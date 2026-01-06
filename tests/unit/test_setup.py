"""Tests for the setup wizard."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from field_agent.cli.setup import (
    check_tmux,
    generate_secret_key,
    save_config,
    load_existing_config,
    get_tmux_install_instructions,
    DEFAULT_CONFIG_FILE,
)


class TestCheckTmux:
    """Tests for tmux detection."""

    def test_tmux_found(self):
        """Test when tmux is installed."""
        with patch("shutil.which", return_value="/usr/bin/tmux"):
            assert check_tmux() is True

    def test_tmux_not_found(self):
        """Test when tmux is not installed."""
        with patch("shutil.which", return_value=None):
            assert check_tmux() is False


class TestGenerateSecretKey:
    """Tests for secret key generation."""

    def test_generates_string(self):
        """Test that a string is generated."""
        key = generate_secret_key()
        assert isinstance(key, str)

    def test_minimum_length(self):
        """Test that key is at least 32 characters."""
        key = generate_secret_key()
        assert len(key) >= 32

    def test_unique_each_time(self):
        """Test that each call generates a unique key."""
        key1 = generate_secret_key()
        key2 = generate_secret_key()
        assert key1 != key2


class TestSaveConfig:
    """Tests for saving configuration."""

    def test_creates_directory(self):
        """Test that config directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.yaml"
            save_config(config_path, "secret", "hash")
            assert config_path.parent.exists()

    def test_saves_yaml(self):
        """Test that config is saved as YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            save_config(config_path, "my-secret", "my-hash", "127.0.0.1", 9000)

            with open(config_path) as f:
                data = yaml.safe_load(f)

            assert data["secret_key"] == "my-secret"
            assert data["passphrase_hash"] == "my-hash"
            assert data["host"] == "127.0.0.1"
            assert data["port"] == 9000

    def test_restrictive_permissions(self):
        """Test that config file has restrictive permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            save_config(config_path, "secret", "hash")

            # Check permissions (0o600 = owner read/write only)
            mode = config_path.stat().st_mode & 0o777
            assert mode == 0o600


class TestLoadExistingConfig:
    """Tests for loading existing configuration."""

    def test_returns_none_if_not_exists(self):
        """Test that None is returned if config doesn't exist."""
        result = load_existing_config(Path("/nonexistent/config.yaml"))
        assert result is None

    def test_loads_existing_config(self):
        """Test that existing config is loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("secret_key: test\nport: 8080")

            result = load_existing_config(config_path)
            assert result["secret_key"] == "test"
            assert result["port"] == 8080

    def test_returns_none_on_invalid_yaml(self):
        """Test that None is returned on invalid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("invalid: yaml: content: [")

            result = load_existing_config(config_path)
            assert result is None


class TestGetTmuxInstallInstructions:
    """Tests for OS-specific install instructions."""

    def test_macos_instructions(self):
        """Test macOS instructions."""
        with patch("sys.platform", "darwin"):
            instructions = get_tmux_install_instructions()
            assert "brew" in instructions

    def test_linux_apt_instructions(self):
        """Test Linux apt instructions."""
        with patch("sys.platform", "linux"):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/apt-get" if x == "apt-get" else None):
                instructions = get_tmux_install_instructions()
                assert "apt-get" in instructions

    def test_linux_yum_instructions(self):
        """Test Linux yum instructions."""
        with patch("sys.platform", "linux"):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/yum" if x == "yum" else None):
                instructions = get_tmux_install_instructions()
                assert "yum" in instructions


class TestDefaultConfigPath:
    """Tests for default config path."""

    def test_default_path_in_home(self):
        """Test that default config is in user's home directory."""
        assert str(Path.home()) in str(DEFAULT_CONFIG_FILE)
        assert "field-agent" in str(DEFAULT_CONFIG_FILE)
        assert "config.yaml" in str(DEFAULT_CONFIG_FILE)
