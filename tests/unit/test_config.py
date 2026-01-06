"""Tests for field-agent.config module."""

import os
from pathlib import Path

import pytest

from field_agent.config import Config, ConfigError


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_host(self, clean_env, mock_secret_key):
        """Default host should be 0.0.0.0."""
        config = Config.load()
        assert config.host == "0.0.0.0"

    def test_default_port(self, clean_env, mock_secret_key):
        """Default port should be 8080."""
        config = Config.load()
        assert config.port == 8080

    def test_default_access_token_expire_minutes(self, clean_env, mock_secret_key):
        """Default access token expiry should be 15 minutes."""
        config = Config.load()
        assert config.access_token_expire_minutes == 15

    def test_default_refresh_token_expire_days(self, clean_env, mock_secret_key):
        """Default refresh token expiry should be 7 days."""
        config = Config.load()
        assert config.refresh_token_expire_days == 7


class TestConfigEnvironment:
    """Test configuration loading from environment variables."""

    def test_host_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Host should be loaded from FIELD_AGENT_HOST."""
        monkeypatch.setenv("FIELD_AGENT_HOST", "127.0.0.1")
        config = Config.load()
        assert config.host == "127.0.0.1"

    def test_port_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Port should be loaded from FIELD_AGENT_PORT."""
        monkeypatch.setenv("FIELD_AGENT_PORT", "9000")
        config = Config.load()
        assert config.port == 9000

    def test_secret_key_from_env(self, clean_env, monkeypatch):
        """Secret key should be loaded from FIELD_AGENT_SECRET_KEY."""
        secret = "my-super-secret-key-that-is-long-enough"
        monkeypatch.setenv("FIELD_AGENT_SECRET_KEY", secret)
        config = Config.load()
        assert config.secret_key == secret

    def test_passphrase_hash_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Passphrase hash should be loaded from FIELD_AGENT_PASSPHRASE_HASH."""
        hash_value = "$2b$12$somehashvalue"
        monkeypatch.setenv("FIELD_AGENT_PASSPHRASE_HASH", hash_value)
        config = Config.load()
        assert config.passphrase_hash == hash_value

    def test_access_token_expire_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Access token expiry should be loaded from FIELD_AGENT_ACCESS_TOKEN_EXPIRE_MINUTES."""
        monkeypatch.setenv("FIELD_AGENT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        config = Config.load()
        assert config.access_token_expire_minutes == 30

    def test_refresh_token_expire_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Refresh token expiry should be loaded from FIELD_AGENT_REFRESH_TOKEN_EXPIRE_DAYS."""
        monkeypatch.setenv("FIELD_AGENT_REFRESH_TOKEN_EXPIRE_DAYS", "14")
        config = Config.load()
        assert config.refresh_token_expire_days == 14


class TestConfigYaml:
    """Test configuration loading from YAML file."""

    def test_load_from_yaml(self, clean_env, tmp_path, monkeypatch):
        """Config should be loadable from YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
host: 192.168.1.1
port: 3000
secret_key: yaml-secret-key-that-is-long-enough-for-jwt
access_token_expire_minutes: 60
""")
        monkeypatch.setenv("FIELD_AGENT_CONFIG", str(config_file))
        config = Config.load()
        assert config.host == "192.168.1.1"
        assert config.port == 3000
        assert config.secret_key == "yaml-secret-key-that-is-long-enough-for-jwt"
        assert config.access_token_expire_minutes == 60

    def test_env_overrides_yaml(self, clean_env, tmp_path, monkeypatch):
        """Environment variables should override YAML values."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
host: 192.168.1.1
port: 3000
secret_key: yaml-secret-key-that-is-long-enough-for-jwt
""")
        monkeypatch.setenv("FIELD_AGENT_CONFIG", str(config_file))
        monkeypatch.setenv("FIELD_AGENT_PORT", "5000")
        config = Config.load()
        assert config.host == "192.168.1.1"  # from YAML
        assert config.port == 5000  # from env (override)


class TestConfigValidation:
    """Test configuration validation."""

    def test_missing_secret_key_raises_error(self, clean_env):
        """Missing secret key should raise ConfigError."""
        with pytest.raises(ConfigError, match="secret_key"):
            Config.load()

    def test_secret_key_too_short_raises_error(self, clean_env, monkeypatch):
        """Secret key shorter than 32 characters should raise ConfigError."""
        monkeypatch.setenv("FIELD_AGENT_SECRET_KEY", "short")
        with pytest.raises(ConfigError, match="at least 32 characters"):
            Config.load()

    def test_invalid_port_raises_error(self, clean_env, mock_secret_key, monkeypatch):
        """Invalid port should raise ConfigError."""
        monkeypatch.setenv("FIELD_AGENT_PORT", "not-a-number")
        with pytest.raises(ConfigError, match="port"):
            Config.load()

    def test_port_out_of_range_raises_error(self, clean_env, mock_secret_key, monkeypatch):
        """Port out of range should raise ConfigError."""
        monkeypatch.setenv("FIELD_AGENT_PORT", "99999")
        with pytest.raises(ConfigError, match="port"):
            Config.load()

    def test_validate_returns_errors_list(self, clean_env, mock_secret_key, monkeypatch):
        """validate() should return list of error messages."""
        monkeypatch.setenv("FIELD_AGENT_PORT", "-1")
        config = Config._load_without_validation()
        errors = config.validate()
        assert isinstance(errors, list)
        assert any("port" in error.lower() for error in errors)


class TestConfigProperties:
    """Test computed properties."""

    def test_config_dir_property(self, clean_env, mock_secret_key):
        """config_dir property should return Path to ~/.field_agent."""
        config = Config.load()
        expected = Path.home() / ".field_agent"
        assert config.config_dir == expected

    def test_access_token_expire_seconds(self, clean_env, mock_secret_key, monkeypatch):
        """access_token_expire_seconds should convert minutes to seconds."""
        monkeypatch.setenv("FIELD_AGENT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        config = Config.load()
        assert config.access_token_expire_seconds == 30 * 60

    def test_refresh_token_expire_seconds(self, clean_env, mock_secret_key, monkeypatch):
        """refresh_token_expire_seconds should convert days to seconds."""
        monkeypatch.setenv("FIELD_AGENT_REFRESH_TOKEN_EXPIRE_DAYS", "14")
        config = Config.load()
        assert config.refresh_token_expire_seconds == 14 * 24 * 60 * 60


class TestConfigOptionalFields:
    """Test optional configuration fields."""

    def test_passphrase_hash_optional(self, clean_env, mock_secret_key):
        """Passphrase hash should be optional (None by default)."""
        config = Config.load()
        assert config.passphrase_hash is None

    def test_debug_mode_default_false(self, clean_env, mock_secret_key):
        """Debug mode should default to False."""
        config = Config.load()
        assert config.debug is False

    def test_debug_mode_from_env(self, clean_env, mock_secret_key, monkeypatch):
        """Debug mode should be loadable from env."""
        monkeypatch.setenv("FIELD_AGENT_DEBUG", "true")
        config = Config.load()
        assert config.debug is True

    def test_debug_mode_various_truthy_values(self, clean_env, mock_secret_key, monkeypatch):
        """Debug mode should accept various truthy values."""
        for value in ["true", "True", "TRUE", "1", "yes"]:
            monkeypatch.setenv("FIELD_AGENT_DEBUG", value)
            config = Config.load()
            assert config.debug is True, f"Failed for value: {value}"
