"""Shared pytest fixtures for field-agent tests."""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary config directory."""
    config_dir = tmp_path / ".field_agent"
    config_dir.mkdir()
    yield config_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    """Clear all FIELD_AGENT_ environment variables and prevent config file loading."""
    env_vars = [key for key in os.environ if key.startswith("FIELD_AGENT_")]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)

    # Point to a non-existent config file to prevent auto-loading
    fake_config = tmp_path / "nonexistent" / "config.yaml"
    monkeypatch.setenv("FIELD_AGENT_CONFIG", str(fake_config))
    yield


@pytest.fixture
def mock_secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a test secret key."""
    secret = "test-secret-key-for-jwt-at-least-32-characters-long"
    monkeypatch.setenv("FIELD_AGENT_SECRET_KEY", secret)
    return secret


@pytest.fixture
def mock_passphrase_hash(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a test passphrase hash (for 'testpassphrase123!')."""
    # bcrypt hash for 'testpassphrase123!'
    hash_value = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.wE3k5m5V5m5m5m"
    monkeypatch.setenv("FIELD_AGENT_PASSPHRASE_HASH", hash_value)
    return hash_value
