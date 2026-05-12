# rest-api-template

> Production-grade FastAPI scaffold: **JWT + opaque refresh tokens** (rotated on use, revokable), **APScheduler** background jobs, **OpenTelemetry** instrumentation, **SQLAlchemy 2.0** with Postgres or SQLite. **30/30 pytest cases** pass in 5.5 s with **88 % code coverage**. Cold-start to first `/healthz` 200: **103 ms** (app-only). Sustained 20-concurrent-user workload (register → login → 20 task CRUD ops each): **86 QPS, p50 = 52 ms**.

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Tests](https://img.shields.io/badge/tests-30%20passing-brightgreen)](#tests) [![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen)](#tests) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

## What you get

A FastAPI service that's ready to deploy, not a "hello world" wrapper. Every concern a real backend hits has a named module:

| Concern | Module | What's in it |
|---|---|---|
| Auth | `src/api/services/auth.py` + `routes/auth.py` | register, login, refresh-token rotation, logout, `/me` |
| Tokens | `src/api/services/security.py` | bcrypt password hashing + JWT access tokens with explicit `type: access` claim |
| DB | `src/api/db/session.py` + `models/tables.py` | SQLAlchemy 2 with `DeclarativeBase`, SQLite default, Postgres via DSN |
| Background jobs | `src/api/jobs/scheduler.py` | APScheduler (no Redis broker needed for local dev) with refresh-token GC + active-user metric |
| Tracing | `src/api/telemetry/otel.py` | OpenTelemetry FastAPI + SQLAlchemy instrumentors, OFF by default |
| Config | `src/api/config.py` | pydantic-settings, `REST_API_*` env-var prefix, `.env` support |
| Health | `src/api/routes/health.py` | `/healthz` (liveness) + `/readyz` (DB ping) |

## Hero benchmark

`python bench/run_benchmark.py --concurrency 20 --tasks-per-user 10`

```json
{
  "cold_start": {
    "cold_start_app_only_ms": 103.8,
    "cold_start_total_with_python_boot_ms": 2029.9,
    "first_healthz_status": 200
  },
  "load": {
    "concurrency": 20,
    "tasks_per_user": 10,
    "total_requests": 660,
    "wall_seconds": 7.676,
    "qps": 86.0,
    "latency_ms": {"p50": 52.22, "p95": 817.67, "p99": 2235.69, "mean": 184.55}
  },
  "coverage": {"coverage_percent": 87.97, "lines_covered": 395, "lines_total": 449}
}
```

| Metric | Value | What it means |
|---|---:|---|
| Cold start (app only) | **103.8 ms** | Time from `import api` to first `/healthz` returning 200 |
| Cold start (process boot included) | 2.03 s | Adds Python interpreter + dependency imports — the realistic "kubernetes pod ready" number |
| QPS @ 20 concurrent users | **86** | 20 register → login → 20-tasks-each = 660 total reqs in 7.7 s |
| p50 latency | **52 ms** | The "feels instant" path |
| p99 latency | 2.24 s | **Dominated by concurrent bcrypt registers** — see the honest discussion below |
| Code coverage | **88 %** | `pytest --cov` over the 30-test suite |

### Honest read on the p99

p99 is 2.2 s and p95 is 818 ms — much higher than p50 = 52 ms. The cause is bcrypt: registering 20 users concurrently slams the CPU because **bcrypt at `rounds=10` is intentionally slow** (~80 ms per hash) and Python's GIL serializes the work. This is the right security trade-off for register/login (don't let attackers brute-force passwords cheaply) but it tells you exactly where the next optimisation is:

* Drop `rounds` to 8 for a 4× hash speedup (still strong — Django default is 12).
* Offload bcrypt to a thread pool with `run_in_executor` so the event loop can keep serving non-auth requests.
* Move register/login behind a 429-rate-limited path (see [llm-gateway-mini](https://github.com/Tajaddin/llm-gateway-mini) for the token-bucket pattern).

The benchmark deliberately keeps `rounds=10` and reports the unflattering tail.

## Auth flow

```
POST /register    (email, password)            → 201, user
POST /login       (email, password)            → 200, {access, refresh}
GET  /me          Bearer <access>              → 200, user
POST /refresh     (refresh)                    → 200, {access, refresh}  ← rotates: old refresh revoked
POST /logout      (refresh)                    → 204                      ← refresh revoked
```

Refresh tokens are **opaque random strings stored in DB** (not JWTs) so they can be revoked individually. Each `/refresh` issues a fresh pair and burns the old refresh — no replay possible. The access token is a stateless JWT with `type: access` to prevent it being mistakenly accepted on `/refresh`.

## Background jobs

APScheduler runs in-process. Two example jobs ship:

| Job | Schedule | Action |
|---|---|---|
| `cleanup_expired_refresh_tokens` | every minute | hard-deletes refresh rows whose `expires_at` is past |
| `log_active_user_count` | every 5 minutes | logs the count of active users (the OpenTelemetry tracing example) |

To swap APScheduler for Celery / Dramatiq / RQ, replace `src/api/jobs/scheduler.py`. The job *functions* (e.g. `cleanup_expired_refresh_tokens`) are plain callables — they don't import the scheduler library.

## OpenTelemetry

Off by default. Set `REST_API_OTEL_ENABLED=1` to enable; spans go to a console exporter so you can see them immediately. For production, override `OTEL_EXPORTER_OTLP_*` env vars per the OpenTelemetry SDK spec — the FastAPI and SQLAlchemy instrumentors are already attached.

## Tests

```bash
pytest --cov=src/api
```

```
test_config.py             3 passed   default settings, env-prefix override, short-secret rejection
test_security.py           6 passed   bcrypt roundtrip, corrupt-hash safe, JWT decode, JWT expiry, wrong-secret reject, refresh-token uniqueness
test_health.py             2 passed   /healthz, /readyz with DB ping
test_auth_routes.py       11 passed   register / login / refresh-rotation / logout-revoke / bearer-required / garbage-token
test_task_routes.py        6 passed   CRUD happy-path, 404 missing, cross-user isolation, auth required
test_background_jobs.py    2 passed   cleanup deletes only expired + idempotent on second run
─────────────────────────────────────────────
30 passed in 5.46s
coverage: 88 %  (395 / 449 lines)
```

## Quickstart

```bash
pip install -e ".[dev]"

# Default SQLite — no external infra required.
rest-api --host 0.0.0.0 --port 8000

# Postgres:
pip install -e ".[postgres]"
export REST_API_DATABASE_URL="postgresql+psycopg://user:pw@localhost/db"
rest-api
```

Programmatic embed:

```python
from api import create_app
from api.config import Settings
app = create_app(Settings(database_url="postgresql+psycopg://..."))
```

## Project layout

```
.
├── src/api/
│   ├── app.py              # create_app() factory
│   ├── config.py           # Settings + get_settings()
│   ├── db/session.py       # engine, sessionmaker, FastAPI dependency
│   ├── models/tables.py    # User, RefreshToken, Task
│   ├── services/
│   │   ├── security.py     # bcrypt + JWT
│   │   ├── auth.py         # register/login/refresh/revoke
│   │   └── tasks.py        # task CRUD
│   ├── routes/
│   │   ├── auth.py         # /register /login /refresh /logout /me
│   │   ├── tasks.py        # /tasks CRUD
│   │   └── health.py       # /healthz /readyz
│   ├── jobs/scheduler.py   # APScheduler jobs + functions
│   ├── telemetry/otel.py   # OpenTelemetry setup (optional)
│   └── cli.py              # `rest-api` entrypoint
├── tests/                  # 30 cases across 7 files
└── bench/run_benchmark.py  # cold-start + load + coverage
```

## Limitations

**SQLite default for portability.** The template works against Postgres out of the box (`pip install '.[postgres]'`), but the default `database_url` is SQLite so newcomers can run the test suite with no infrastructure. Concurrent throughput numbers improve significantly with Postgres + multiple Uvicorn workers.

**No Alembic migrations in the bootstrap.** The schema is created from `Base.metadata.create_all` at startup. Production deployments should swap that for `alembic upgrade head` in a startup hook. Alembic is already in `dependencies` — just `alembic init alembic` and import `Base` from `api.db.session`.

**APScheduler is in-process.** It runs on the same process as the API. For multi-replica deployments, swap to Celery or a dedicated worker pod. The job *functions* don't need to change.

**OpenTelemetry uses console exporter when enabled.** Production wires `OTEL_EXPORTER_OTLP_ENDPOINT` and you get OTLP-over-HTTP to Honeycomb/Jaeger/Tempo. The console exporter is for local development visibility.

**JWT secret minimum is 8 chars; HS256 likes 32+.** The test suite uses a 32-char secret to avoid the warning. The default `dev-secret-change-me` is intentionally insecure to force operators to set their own.

## License

MIT — see [LICENSE](LICENSE).
