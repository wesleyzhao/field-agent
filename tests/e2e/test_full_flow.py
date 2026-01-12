"""End-to-end tests for the full field-agent user flow.

Tests the complete journey:
1. Setup wizard creates config
2. Server starts with auto-loaded config
3. Health endpoint works
4. Authentication works
5. Sessions API works (with auth)
"""

import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import yaml


@pytest.fixture
def temp_home(tmp_path):
    """Create a temporary home directory with config."""
    config_dir = tmp_path / ".config" / "field-agent"
    config_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def test_config(temp_home):
    """Create a test configuration file."""
    from field_agent.auth import PassphraseHasher

    hasher = PassphraseHasher()
    passphrase = "test-passphrase-123"
    passphrase_hash = hasher.hash_passphrase(passphrase)

    config = {
        "secret_key": "test-secret-key-must-be-at-least-32-characters-long",
        "passphrase_hash": passphrase_hash,
        "host": "127.0.0.1",
        "port": 18080,  # Use non-standard port to avoid conflicts
    }

    config_file = temp_home / ".config" / "field-agent" / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    return {
        "config_file": config_file,
        "passphrase": passphrase,
        "port": config["port"],
        "home": temp_home,
    }


class TestSetupWizard:
    """Tests for the setup wizard components."""

    def test_setup_creates_config_directory(self, temp_home):
        """Test that setup creates the config directory."""
        from field_agent.cli.setup import save_config

        config_path = temp_home / ".config" / "field-agent" / "nested" / "config.yaml"
        save_config(config_path, "secret-key-32-chars-minimum-here!", "hash")

        assert config_path.exists()
        assert config_path.parent.exists()

    def test_setup_saves_valid_yaml(self, temp_home):
        """Test that setup saves valid YAML config."""
        from field_agent.cli.setup import save_config

        config_path = temp_home / ".config" / "field-agent" / "config.yaml"
        save_config(
            config_path,
            "my-secret-key-at-least-32-characters",
            "$2b$12$hashhere",
            "0.0.0.0",
            8080,
        )

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["secret_key"] == "my-secret-key-at-least-32-characters"
        assert data["passphrase_hash"] == "$2b$12$hashhere"
        assert data["host"] == "0.0.0.0"
        assert data["port"] == 8080

    def test_setup_restricts_permissions(self, temp_home):
        """Test that config file has restricted permissions."""
        from field_agent.cli.setup import save_config

        config_path = temp_home / ".config" / "field-agent" / "config.yaml"
        save_config(config_path, "secret-key-32-chars-minimum-here!", "hash")

        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


class TestConfigAutoLoad:
    """Tests for automatic config loading."""

    def test_config_loads_from_default_path(self, test_config):
        """Test that config auto-loads from ~/.config/field-agent/config.yaml."""
        # Patch Path.home to return our temp directory
        with patch.object(Path, "home", return_value=test_config["home"]):
            # Need to reload the module to pick up the patched home
            from field_agent import config as config_module
            import importlib
            importlib.reload(config_module)

            from field_agent.config import Config
            config = Config.load()

            assert config.port == test_config["port"]
            assert config.host == "127.0.0.1"
            assert len(config.secret_key) >= 32


class TestServerStartup:
    """Tests for server startup with auto-loaded config."""

    @pytest.fixture
    def server_process(self, test_config):
        """Start the server as a subprocess."""
        env = os.environ.copy()
        env["FIELD_AGENT_CONFIG"] = str(test_config["config_file"])

        # Start server
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "field_agent.server.app:app",
                "--host", "127.0.0.1",
                "--port", str(test_config["port"]),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        max_wait = 10
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{test_config['port']}/health",
                    timeout=1,
                )
                if response.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            time.sleep(0.5)

        yield proc

        # Cleanup
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def test_health_endpoint(self, server_process, test_config):
        """Test that health endpoint responds."""
        response = httpx.get(
            f"http://127.0.0.1:{test_config['port']}/health",
            timeout=5,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_login_with_correct_passphrase(self, server_process, test_config):
        """Test that login works with correct passphrase."""
        response = httpx.post(
            f"http://127.0.0.1:{test_config['port']}/auth/login",
            json={"passphrase": test_config["passphrase"]},
            timeout=5,
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_with_wrong_passphrase(self, server_process, test_config):
        """Test that login fails with wrong passphrase."""
        response = httpx.post(
            f"http://127.0.0.1:{test_config['port']}/auth/login",
            json={"passphrase": "wrong-passphrase"},
            timeout=5,
        )
        assert response.status_code == 401

    def test_sessions_requires_auth(self, server_process, test_config):
        """Test that sessions endpoint requires authentication."""
        response = httpx.get(
            f"http://127.0.0.1:{test_config['port']}/sessions",
            timeout=5,
        )
        assert response.status_code == 401

    def test_sessions_with_auth(self, server_process, test_config):
        """Test that sessions endpoint works with authentication."""
        # First login
        login_response = httpx.post(
            f"http://127.0.0.1:{test_config['port']}/auth/login",
            json={"passphrase": test_config["passphrase"]},
            timeout=5,
        )
        token = login_response.json()["access_token"]

        # Then access sessions
        response = httpx.get(
            f"http://127.0.0.1:{test_config['port']}/sessions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data


class TestTunnelProvider:
    """Tests for tunnel provider abstraction."""

    def test_cloudflare_provider_instantiates(self):
        """Test that Cloudflare provider can be instantiated."""
        from field_agent.tunnels import CloudflareTunnelProvider

        provider = CloudflareTunnelProvider()
        assert provider.name == "Cloudflare Tunnel"

    def test_provider_reports_availability(self):
        """Test that provider reports cloudflared availability."""
        from field_agent.tunnels import CloudflareTunnelProvider

        provider = CloudflareTunnelProvider()
        # Just verify it returns a boolean without error
        assert isinstance(provider.is_available, bool)

    def test_provider_has_install_instructions(self):
        """Test that provider provides install instructions."""
        from field_agent.tunnels import CloudflareTunnelProvider

        provider = CloudflareTunnelProvider()
        instructions = provider.get_install_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 0
