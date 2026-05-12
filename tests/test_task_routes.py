"""Integration tests for the task CRUD endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture()
def auth_headers(client) -> dict:
    client.post("/register", json={"email": "tasker@example.com", "password": "supersecret1"})
    pair = client.post("/login", json={"email": "tasker@example.com", "password": "supersecret1"}).json()
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_create_then_list_task(client, auth_headers):
    r = client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    assert r.status_code == 201
    listed = client.get("/tasks", headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["title"] == "first"


def test_get_missing_returns_404(client, auth_headers):
    r = client.get("/tasks/9999", headers=auth_headers)
    assert r.status_code == 404


def test_patch_marks_done(client, auth_headers):
    created = client.post("/tasks", json={"title": "do me"}, headers=auth_headers).json()
    r = client.patch(f"/tasks/{created['id']}", json={"done": True}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_delete_removes_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "delete me"}, headers=auth_headers).json()
    r = client.delete(f"/tasks/{created['id']}", headers=auth_headers)
    assert r.status_code == 204
    r2 = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert r2.status_code == 404


def test_other_user_cannot_see_my_tasks(client):
    client.post("/register", json={"email": "alice@example.com", "password": "supersecret1"})
    alice_pair = client.post("/login", json={"email": "alice@example.com", "password": "supersecret1"}).json()
    alice_h = {"Authorization": f"Bearer {alice_pair['access_token']}"}
    client.post("/tasks", json={"title": "alice's private"}, headers=alice_h)

    client.post("/register", json={"email": "bob@example.com", "password": "supersecret1"})
    bob_pair = client.post("/login", json={"email": "bob@example.com", "password": "supersecret1"}).json()
    bob_h = {"Authorization": f"Bearer {bob_pair['access_token']}"}
    listed = client.get("/tasks", headers=bob_h).json()
    assert listed == []


def test_task_routes_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
