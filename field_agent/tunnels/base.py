"""Base class for tunnel providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class TunnelError(Exception):
    """Error from tunnel operations."""

    pass


@dataclass
class TunnelInfo:
    """Information about an active tunnel."""

    url: str
    provider: str
    local_port: int


class TunnelProvider(ABC):
    """Abstract base class for tunnel providers.

    Tunnel providers expose a local port to the internet, allowing
    remote access to field-agent without firewall configuration.

    Implementations:
    - CloudflareTunnelProvider: Free quick tunnels via cloudflared
    - TailscaleTunnelProvider: Mesh VPN via Tailscale Funnel (future)
    - NgrokTunnelProvider: ngrok tunnels (future)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this provider."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider's CLI tool is installed."""
        ...

    @abstractmethod
    async def start(self, port: int) -> TunnelInfo:
        """Start a tunnel to the specified local port.

        Args:
            port: Local port to tunnel to

        Returns:
            TunnelInfo with public URL and details

        Raises:
            TunnelError: If tunnel cannot be started
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the active tunnel.

        Raises:
            TunnelError: If tunnel cannot be stopped
        """
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Check if a tunnel is currently running."""
        ...

    @abstractmethod
    def get_info(self) -> Optional[TunnelInfo]:
        """Get info about the current tunnel, if running."""
        ...

    async def install(self) -> bool:
        """Attempt to install the tunnel CLI tool.

        Returns:
            True if installation succeeded, False otherwise

        Default implementation returns False (manual install required).
        """
        return False

    def get_install_instructions(self) -> str:
        """Get instructions for installing the tunnel CLI tool.

        Returns:
            Human-readable installation instructions
        """
        return f"Please install the {self.name} CLI tool manually."
