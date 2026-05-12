"""Hero benchmark for rest-api-template.

Measures three numbers worth pinning to a CV:

1. **Cold-start latency** — wall-clock from process spawn to first 200 OK on
   ``/healthz`` (run as a subprocess so import time + DB init are real).
2. **Throughput + p50/p95/p99 latency** under concurrent load through the
   ASGI transport — register / login / 50 task CRUD reqs per "user", with
   ``--concurrency`` simulated users running in parallel.
3. **Test coverage %** via ``pytest --cov`` (parsed from the report).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.app import create_app
from api.config import Settings
from api.db.session import drop_all, init_engine


RESULTS = Path(__file__).resolve().parent / "results.json"


async def _user_workflow(client: httpx.AsyncClient, idx: int, n_tasks: int, latencies: list[float]) -> None:
    email = f"bench-{idx}-{int(time.time()*1000)}@example.com"
    pw = "supersecret1"

    async def _timed(coro):
        t0 = time.perf_counter()
        r = await coro
        latencies.append((time.perf_counter() - t0) * 1000.0)
        return r

    await _timed(client.post("/register", json={"email": email, "password": pw}))
    login = await _timed(client.post("/login", json={"email": email, "password": pw}))
    if login.status_code != 200:
        return
    pair = login.json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    for k in range(n_tasks):
        created = await _timed(client.post("/tasks", json={"title": f"t{k}"}, headers=headers))
        if created.status_code != 201:
            continue
        tid = created.json()["id"]
        await _timed(client.get(f"/tasks/{tid}", headers=headers))
        await _timed(client.patch(f"/tasks/{tid}", json={"done": True}, headers=headers))
    await _timed(client.get("/tasks", headers=headers))


async def run_load(concurrency: int, n_tasks_per_user: int) -> dict:
    settings = Settings(database_url="sqlite:///./bench.sqlite", jwt_secret="x" * 32)
    init_engine(settings)
    drop_all()
    app = create_app(settings, create_tables=True)

    latencies: list[float] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bench") as client:
        t0 = time.perf_counter()
        await asyncio.gather(
            *(_user_workflow(client, i, n_tasks_per_user, latencies) for i in range(concurrency))
        )
        wall = time.perf_counter() - t0

    s = sorted(latencies)
    def pct(p: float) -> float:
        return round(s[min(len(s) - 1, max(0, int(p * (len(s) - 1))))], 2)

    return {
        "concurrency": concurrency,
        "tasks_per_user": n_tasks_per_user,
        "total_requests": len(latencies),
        "wall_seconds": round(wall, 3),
        "qps": round(len(latencies) / max(wall, 1e-9), 1),
        "latency_ms": {
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(max(s), 2),
            "mean": round(statistics.mean(s), 2),
        },
    }


def measure_cold_start() -> dict:
    """Spawn a server, hit /healthz, record time-to-first-200."""
    code = (
        "import sys, time; "
        "sys.path.insert(0, 'src'); "
        "from fastapi.testclient import TestClient; "
        "from api.app import create_app; "
        "from api.config import Settings; "
        "t0 = time.perf_counter(); "
        "app = create_app(Settings(database_url='sqlite:///cold.sqlite'), create_tables=True); "
        "c = TestClient(app); "
        "r = c.get('/healthz'); "
        "print(round((time.perf_counter()-t0)*1000, 1)); "
        "print(r.status_code)"
    )
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    elapsed_total = (time.perf_counter() - t0) * 1000.0
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    elapsed_app = float(lines[0]) if lines else 0.0
    status = int(lines[1]) if len(lines) > 1 else 0
    return {
        "cold_start_app_only_ms": elapsed_app,
        "cold_start_total_with_python_boot_ms": round(elapsed_total, 1),
        "first_healthz_status": status,
    }


def measure_coverage() -> dict:
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            "--cov=src/api",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=json:bench/coverage.json",
        ],
        capture_output=True, text=True, timeout=300,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    cov_file = Path(__file__).resolve().parents[1] / "bench" / "coverage.json"
    if cov_file.exists():
        with cov_file.open(encoding="utf-8") as f:
            data = json.load(f)
        pct = round(float(data["totals"]["percent_covered"]), 2)
        return {
            "coverage_percent": pct,
            "lines_covered": int(data["totals"]["covered_lines"]),
            "lines_total": int(data["totals"]["num_statements"]),
        }
    return {"coverage_percent": 0.0, "lines_covered": 0, "lines_total": 0, "note": "no coverage report"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--tasks-per-user", type=int, default=20)
    args = ap.parse_args()

    print("=== cold start ===")
    cs = measure_cold_start()
    print(json.dumps(cs, indent=2))

    print("=== load ===")
    load = asyncio.run(run_load(args.concurrency, args.tasks_per_user))
    print(json.dumps(load, indent=2))

    print("=== coverage ===")
    cov = measure_coverage()
    print(json.dumps(cov, indent=2))

    out = {"cold_start": cs, "load": load, "coverage": cov}
    RESULTS.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
