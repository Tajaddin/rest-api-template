"""``rest-api`` entrypoint tests."""

from __future__ import annotations

import sys

from api import cli


def _run_cli(monkeypatch, argv: list[str]) -> dict:
    seen: dict = {}
    monkeypatch.setattr(cli, "create_app", lambda: object())
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: seen.update(kw))
    monkeypatch.setattr(sys, "argv", ["rest-api", *argv])
    cli.main()
    return seen


def test_cli_binds_loopback_by_default(monkeypatch):
    assert _run_cli(monkeypatch, [])["host"] == "127.0.0.1"


def test_cli_host_flag_still_allows_all_interfaces(monkeypatch):
    assert _run_cli(monkeypatch, ["--host", "0.0.0.0"])["host"] == "0.0.0.0"
