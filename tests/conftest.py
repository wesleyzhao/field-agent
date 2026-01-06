"""Shared pytest fixtures for termweave tests."""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary config directory."""
    config_dir = tmp_path / ".termweave"
    config_dir.mkdir()
    yield config_dir


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Clear all TERMWEAVE_ environment variables."""
    env_vars = [key for key in os.environ if key.startswith("TERMWEAVE_")]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def mock_secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a test secret key."""
    secret = "test-secret-key-for-jwt-at-least-32-characters-long"
    monkeypatch.setenv("TERMWEAVE_SECRET_KEY", secret)
    return secret


@pytest.fixture
def mock_passphrase_hash(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a test passphrase hash (for 'testpassphrase123!')."""
    # bcrypt hash for 'testpassphrase123!'
    hash_value = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.wE3k5m5V5m5m5m"
    monkeypatch.setenv("TERMWEAVE_PASSPHRASE_HASH", hash_value)
    return hash_value
