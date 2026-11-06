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


def test_refresh_tokens_are_not_stored_in_plaintext(client):
    import hashlib

    from sqlalchemy import text

    from api.db.session import session_scope

    client.post("/register", json={"email": "hash@example.com", "password": "supersecret1"})
    rt = client.post("/login", json={"email": "hash@example.com", "password": "supersecret1"}).json()[
        "refresh_token"
    ]
    with session_scope() as db:
        rows = db.execute(text("SELECT * FROM refresh_tokens")).all()
    assert len(rows) == 1
    stored = [str(v) for v in rows[0]]
    assert rt not in stored
    assert hashlib.sha256(rt.encode()).hexdigest() in stored


def _login(client, email: str) -> dict:
    client.post("/register", json={"email": email, "password": "supersecret1"})
    return client.post("/login", json={"email": email, "password": "supersecret1"}).json()


def test_racing_refreshes_of_one_token_succeed_only_once(client, settings):
    import pytest

    from api.db.session import get_session
    from api.models.tables import RefreshToken
    from api.services.auth import AuthError, rotate_refresh_token

    rt = _login(client, "race@example.com")["refresh_token"]
    # A second request reads the token row, then loses the CPU before writing.
    # Holding the loaded rows keeps them in its identity map, i.e. its stale view.
    slow = next(get_session())
    try:
        stale_view = slow.query(RefreshToken).all()
        assert stale_view
        assert client.post("/refresh", json={"refresh_token": rt}).status_code == 200
        with pytest.raises(AuthError):
            rotate_refresh_token(slow, rt, settings)
    finally:
        slow.close()


def test_reusing_a_rotated_refresh_token_revokes_its_family(client):
    first = _login(client, "reuse@example.com")
    other_device = client.post(
        "/login", json={"email": "reuse@example.com", "password": "supersecret1"}
    ).json()
    second = client.post("/refresh", json={"refresh_token": first["refresh_token"]}).json()

    # The old token shows up again: either the client or a thief has a copy.
    assert client.post("/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401
    # Sessions started by a separate login are a different family and survive.
    assert client.post("/refresh", json={"refresh_token": other_device["refresh_token"]}).status_code == 200
