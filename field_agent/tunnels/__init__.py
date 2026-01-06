"""Tunnel providers for remote access to field-agent."""

from field_agent.tunnels.base import TunnelProvider, TunnelError, TunnelInfo
from field_agent.tunnels.cloudflare import CloudflareTunnelProvider

__all__ = ["TunnelProvider", "TunnelError", "TunnelInfo", "CloudflareTunnelProvider"]


def get_default_provider() -> TunnelProvider:
    """Get the default tunnel provider (Cloudflare)."""
    return CloudflareTunnelProvider()
