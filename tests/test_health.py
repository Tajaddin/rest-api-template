"""Health endpoint tests."""

from __future__ import annotations


def test_healthz_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_returns_ready(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ready"
    assert j["db"] == "up"
