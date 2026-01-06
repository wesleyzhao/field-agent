"""Configuration management for field-agent.

Loads configuration from environment variables and optional YAML file.
Environment variables override YAML values.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class ConfigError(Exception):
    """Configuration error."""

    pass


@dataclass
class Config:
    """Termweave configuration.

    Configuration is loaded from:
    1. Default values
    2. YAML file (if FIELD_AGENT_CONFIG is set)
    3. Environment variables (override YAML)
    """

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Authentication
    secret_key: str = ""
    passphrase_hash: Optional[str] = None
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @property
    def config_dir(self) -> Path:
        """Return path to config directory (~/.field_agent)."""
        return Path.home() / ".field_agent"

    @property
    def access_token_expire_seconds(self) -> int:
        """Return access token expiry in seconds."""
        return self.access_token_expire_minutes * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        """Return refresh token expiry in seconds."""
        return self.refresh_token_expire_days * 24 * 60 * 60

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.secret_key:
            errors.append("secret_key is required")
        elif len(self.secret_key) < 32:
            errors.append("secret_key must be at least 32 characters")

        if not isinstance(self.port, int):
            errors.append("port must be an integer")
        elif self.port < 1 or self.port > 65535:
            errors.append("port must be between 1 and 65535")

        if self.access_token_expire_minutes < 1:
            errors.append("access_token_expire_minutes must be at least 1")

        if self.refresh_token_expire_days < 1:
            errors.append("refresh_token_expire_days must be at least 1")

        return errors

    @classmethod
    def _load_without_validation(cls) -> "Config":
        """Load config without validation (for testing)."""
        config = cls()
        config = cls._load_from_yaml(config)
        config = cls._load_from_env(config)
        return config

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment and optional YAML file.

        Raises:
            ConfigError: If configuration is invalid.
        """
        config = cls._load_without_validation()

        errors = config.validate()
        if errors:
            raise ConfigError("; ".join(errors))

        return config

    @classmethod
    def _load_from_yaml(cls, config: "Config") -> "Config":
        """Load configuration from YAML file.

        Checks in order:
        1. FIELD_AGENT_CONFIG env var (explicit path)
        2. ~/.config/field-agent/config.yaml (default location)
        """
        # Check for explicit config path
        config_path = os.environ.get("FIELD_AGENT_CONFIG")

        if config_path:
            path = Path(config_path)
        else:
            # Default to ~/.config/field-agent/config.yaml
            path = Path.home() / ".config" / "field-agent" / "config.yaml"

        if not path.exists():
            return config

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigError(f"Failed to load config file: {e}")

        # Apply YAML values
        if "host" in data:
            config.host = str(data["host"])
        if "port" in data:
            config.port = int(data["port"])
        if "debug" in data:
            config.debug = cls._parse_bool(data["debug"])
        if "secret_key" in data:
            config.secret_key = str(data["secret_key"])
        if "passphrase_hash" in data:
            config.passphrase_hash = str(data["passphrase_hash"])
        if "access_token_expire_minutes" in data:
            config.access_token_expire_minutes = int(data["access_token_expire_minutes"])
        if "refresh_token_expire_days" in data:
            config.refresh_token_expire_days = int(data["refresh_token_expire_days"])

        return config

    @classmethod
    def _load_from_env(cls, config: "Config") -> "Config":
        """Load configuration from environment variables."""
        env_mappings = {
            "FIELD_AGENT_HOST": ("host", str),
            "FIELD_AGENT_PORT": ("port", cls._parse_port),
            "FIELD_AGENT_DEBUG": ("debug", cls._parse_bool),
            "FIELD_AGENT_SECRET_KEY": ("secret_key", str),
            "FIELD_AGENT_PASSPHRASE_HASH": ("passphrase_hash", str),
            "FIELD_AGENT_ACCESS_TOKEN_EXPIRE_MINUTES": ("access_token_expire_minutes", int),
            "FIELD_AGENT_REFRESH_TOKEN_EXPIRE_DAYS": ("refresh_token_expire_days", int),
        }

        for env_var, (attr, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(config, attr, converter(value))
                except (ValueError, TypeError) as e:
                    raise ConfigError(f"Invalid value for {env_var}: {e}")

        return config

    @staticmethod
    def _parse_bool(value: str | bool) -> bool:
        """Parse a boolean value from string or bool."""
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _parse_port(value: str) -> int:
        """Parse port value (validation happens in validate())."""
        try:
            return int(value)
        except ValueError:
            raise ConfigError(f"Invalid port value: {value}")
