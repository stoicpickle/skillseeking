from __future__ import annotations

from app.env_utils import safe_env


def test_safe_env_excludes_home_by_default(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/home")
    monkeypatch.setenv("PATH", "/bin")
    monkeypatch.setenv("SECRET_TOKEN", "nope")

    env = safe_env()

    assert env["PATH"] == "/bin"
    assert "HOME" not in env
    assert "SECRET_TOKEN" not in env


def test_safe_env_can_include_home(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/home")

    env = safe_env(include_home=True)

    assert env["HOME"] == "/tmp/home"

