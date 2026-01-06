"""Cloudflare Tunnel provider using cloudflared CLI."""

import asyncio
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from field_agent.tunnels.base import TunnelError, TunnelInfo, TunnelProvider


class CloudflareTunnelProvider(TunnelProvider):
    """Tunnel provider using Cloudflare's free quick tunnels.

    Uses the `cloudflared` CLI tool to create temporary tunnels.
    No Cloudflare account required for quick tunnels.

    Quick tunnels provide a random subdomain like:
    https://random-words-here.trycloudflare.com
    """

    def __init__(self):
        """Initialize the Cloudflare tunnel provider."""
        self._process: Optional[subprocess.Popen] = None
        self._tunnel_url: Optional[str] = None
        self._local_port: Optional[int] = None

    @property
    def name(self) -> str:
        """Human-readable name of this provider."""
        return "Cloudflare Tunnel"

    @property
    def is_available(self) -> bool:
        """Check if cloudflared is installed."""
        return shutil.which("cloudflared") is not None

    def _get_cloudflared_path(self) -> Optional[str]:
        """Get path to cloudflared binary."""
        # Check system PATH first
        path = shutil.which("cloudflared")
        if path:
            return path

        # Check common installation locations
        common_paths = [
            Path.home() / ".local" / "bin" / "cloudflared",
            Path("/usr/local/bin/cloudflared"),
            Path("/usr/bin/cloudflared"),
        ]

        for p in common_paths:
            if p.exists() and os.access(p, os.X_OK):
                return str(p)

        return None

    async def start(self, port: int) -> TunnelInfo:
        """Start a quick tunnel to the specified port.

        Args:
            port: Local port to tunnel to

        Returns:
            TunnelInfo with public URL

        Raises:
            TunnelError: If tunnel cannot be started
        """
        if self._process is not None and self._process.poll() is None:
            raise TunnelError("Tunnel is already running")

        cloudflared = self._get_cloudflared_path()
        if not cloudflared:
            raise TunnelError(
                "cloudflared not found. Install it with:\n"
                f"  {self.get_install_instructions()}"
            )

        # Start cloudflared tunnel
        cmd = [
            cloudflared,
            "tunnel",
            "--url",
            f"http://localhost:{port}",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            raise TunnelError(f"Failed to start cloudflared: {e}")

        # Wait for URL to appear in output
        self._tunnel_url = await self._wait_for_url(timeout=30)
        self._local_port = port

        return TunnelInfo(
            url=self._tunnel_url,
            provider=self.name,
            local_port=port,
        )

    async def _wait_for_url(self, timeout: int = 30) -> str:
        """Wait for cloudflared to output the tunnel URL.

        The URL appears in stderr in a line like:
        | https://random-words.trycloudflare.com |
        """
        if self._process is None:
            raise TunnelError("Process not started")

        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        start_time = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                self._kill_process()
                raise TunnelError(f"Timeout waiting for tunnel URL after {timeout}s")

            # Check if process died
            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise TunnelError(f"cloudflared exited unexpectedly: {stderr}")

            # Read stderr (cloudflared outputs URL there)
            if self._process.stderr:
                line = self._process.stderr.readline()
                if line:
                    match = url_pattern.search(line)
                    if match:
                        return match.group(0)

            await asyncio.sleep(0.1)

    def _kill_process(self) -> None:
        """Kill the cloudflared process."""
        if self._process is not None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception:
                pass
            finally:
                self._process = None

    async def stop(self) -> None:
        """Stop the tunnel."""
        if self._process is None:
            return

        self._kill_process()
        self._tunnel_url = None
        self._local_port = None

    def is_running(self) -> bool:
        """Check if tunnel is running."""
        return self._process is not None and self._process.poll() is None

    def get_info(self) -> Optional[TunnelInfo]:
        """Get info about the current tunnel."""
        if not self.is_running() or not self._tunnel_url or not self._local_port:
            return None

        return TunnelInfo(
            url=self._tunnel_url,
            provider=self.name,
            local_port=self._local_port,
        )

    async def install(self) -> bool:
        """Attempt to install cloudflared.

        Returns:
            True if installation succeeded
        """
        system = platform.system().lower()

        try:
            if system == "darwin":
                # macOS - use Homebrew
                result = subprocess.run(
                    ["brew", "install", "cloudflared"],
                    capture_output=True,
                    timeout=120,
                )
                return result.returncode == 0

            elif system == "linux":
                # Linux - download binary
                arch = platform.machine()
                if arch == "x86_64":
                    arch = "amd64"
                elif arch == "aarch64":
                    arch = "arm64"

                url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
                dest = Path.home() / ".local" / "bin" / "cloudflared"
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Download binary
                result = subprocess.run(
                    ["curl", "-fsSL", "-o", str(dest), url],
                    capture_output=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    return False

                # Make executable
                os.chmod(dest, 0o755)
                return True

        except Exception:
            pass

        return False

    def get_install_instructions(self) -> str:
        """Get installation instructions for cloudflared."""
        system = platform.system().lower()

        if system == "darwin":
            return "brew install cloudflared"
        elif system == "linux":
            return (
                "curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "
                "-o ~/.local/bin/cloudflared && chmod +x ~/.local/bin/cloudflared"
            )
        else:
            return "Visit https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation"
