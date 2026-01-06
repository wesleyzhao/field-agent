"""Abstract base class for server providers.

This module defines the interface for server providers, allowing
field-agent to manage sessions across multiple servers in the future.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional


@dataclass
class Session:
    """Represents a terminal session."""

    id: str
    name: str
    server: str
    created_at: datetime
    attached: bool
    windows: int = 1
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "server": self.server,
            "created_at": self.created_at.isoformat(),
            "attached": self.attached,
            "windows": self.windows,
            "width": self.width,
            "height": self.height,
        }


class ServerProvider(ABC):
    """Abstract interface for server operations.

    MVP: LocalServerProvider for same-machine tmux.
    Future: SSHServerProvider, GCPServerProvider for remote servers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this server."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether provider can communicate with server."""
        pass

    @abstractmethod
    async def list_sessions(self) -> list[Session]:
        """List all tmux sessions on this server."""
        pass

    @abstractmethod
    async def create_session(self, name: Optional[str] = None) -> Session:
        """Create a new tmux session."""
        pass

    @abstractmethod
    async def kill_session(self, session_id: str) -> bool:
        """Kill a session. Returns True if killed."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a specific session by ID."""
        pass

    @abstractmethod
    async def get_attach_command(self, session_id: str) -> list[str]:
        """Get the command to attach to a session.

        Returns:
            Command list suitable for subprocess/pty
        """
        pass
