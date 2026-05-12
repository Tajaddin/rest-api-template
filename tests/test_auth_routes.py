"""Integration tests for /register, /login, /refresh, /logout, /me."""

from __future__ import annotations


def test_register_creates_user(client):
    r = client.post("/register", json={"email": "alice@example.com", "password": "supersecret1"})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["email"] == "alice@example.com"
    assert j["is_active"] is True


def test_register_rejects_duplicate_email(client):
    payload = {"email": "bob@example.com", "password": "supersecret1"}
    assert client.post("/register", json=payload).status_code == 201
    r = client.post("/register", json=payload)
    assert r.status_code == 409


def test_register_rejects_short_password(client):
    r = client.post("/register", json={"email": "weak@example.com", "password": "x"})
    assert r.status_code == 422


def test_login_returns_token_pair(client):
    client.post("/register", json={"email": "carol@example.com", "password": "supersecret1"})
    r = client.post("/login", json={"email": "carol@example.com", "password": "supersecret1"})
    assert r.status_code == 200
    j = r.json()
    assert "access_token" in j and "refresh_token" in j
    assert j["token_type"] == "bearer"


def test_login_wrong_password_returns_401(client):
    client.post("/register", json={"email": "dave@example.com", "password": "supersecret1"})
    r = client.post("/login", json={"email": "dave@example.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401(client):
    r = client.post("/login", json={"email": "nobody@example.com", "password": "anything"})
    assert r.status_code == 401


def test_me_requires_bearer_token(client):
    r = client.get("/me")
    assert r.status_code == 401


def test_me_with_valid_token_returns_user(client):
    client.post("/register", json={"email": "eve@example.com", "password": "supersecret1"})
    login = client.post("/login", json={"email": "eve@example.com", "password": "supersecret1"})
    access = login.json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == "eve@example.com"


def test_refresh_rotates_tokens(client):
    client.post("/register", json={"email": "fred@example.com", "password": "supersecret1"})
    pair = client.post("/login", json={"email": "fred@example.com", "password": "supersecret1"}).json()
    r = client.post("/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 200
    new_pair = r.json()
    assert new_pair["refresh_token"] != pair["refresh_token"]
    # The old refresh token must now be revoked.
    r2 = client.post("/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r2.status_code == 401


def test_logout_revokes_refresh(client):
    client.post("/register", json={"email": "gina@example.com", "password": "supersecret1"})
    pair = client.post("/login", json={"email": "gina@example.com", "password": "supersecret1"}).json()
    r = client.post("/logout", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 204
    r2 = client.post("/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r2.status_code == 401


def test_bearer_token_with_garbage_rejected(client):
    r = client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
