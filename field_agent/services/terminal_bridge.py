"""Terminal bridge for WebSocket to PTY communication."""

import asyncio
import fcntl
import os
import pty
import struct
import termios
from typing import Optional

from field_agent.providers.base import ServerProvider


class TerminalBridge:
    """Bridges a PTY to a WebSocket connection.

    This class manages the PTY subprocess and handles bidirectional
    communication between the WebSocket and the tmux attach process.
    """

    def __init__(self, provider: ServerProvider, session_id: str):
        """Initialize the terminal bridge.

        Args:
            provider: The server provider to use
            session_id: The session ID to attach to
        """
        self.provider = provider
        self.session_id = session_id
        self.pty_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self._running = False

    async def start(self) -> None:
        """Start the tmux attach process with a PTY."""
        command = await self.provider.get_attach_command(self.session_id)

        # Fork a new process with a PTY
        pid, fd = pty.fork()

        if pid == 0:
            # Child process - exec the tmux attach command
            os.execvp(command[0], command)
        else:
            # Parent process
            self.pid = pid
            self.pty_fd = fd
            self._running = True

            # Set non-blocking mode on the PTY
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def read_output(self) -> bytes:
        """Read output from the PTY.

        Returns:
            Bytes read from the PTY, or empty bytes if nothing available
        """
        if self.pty_fd is None:
            return b""

        try:
            # Use asyncio to read in a non-blocking way
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._read_pty)
            return data
        except (OSError, IOError):
            return b""

    def _read_pty(self) -> bytes:
        """Synchronous PTY read."""
        if self.pty_fd is None:
            return b""
        try:
            return os.read(self.pty_fd, 4096)
        except (BlockingIOError, OSError):
            return b""

    async def write_input(self, data: bytes) -> None:
        """Write input to the PTY.

        Args:
            data: Bytes to write to the PTY
        """
        if self.pty_fd is None:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, os.write, self.pty_fd, data)
        except (OSError, IOError):
            pass

    def resize(self, cols: int, rows: int) -> None:
        """Resize the terminal.

        Args:
            cols: Number of columns
            rows: Number of rows
        """
        if self.pty_fd is None:
            return

        try:
            # Set the window size using TIOCSWINSZ ioctl
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.pty_fd, termios.TIOCSWINSZ, winsize)
        except (OSError, IOError):
            pass

    async def close(self) -> None:
        """Clean up the PTY and child process."""
        self._running = False

        if self.pty_fd is not None:
            try:
                os.close(self.pty_fd)
            except OSError:
                pass
            self.pty_fd = None

        if self.pid is not None:
            try:
                os.kill(self.pid, 9)  # SIGKILL
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.pid = None

    @property
    def is_running(self) -> bool:
        """Check if the bridge is still running."""
        if not self._running or self.pid is None:
            return False

        try:
            # Check if child process is still alive
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid != 0:
                # Process has exited
                self._running = False
                return False
            return True
        except (OSError, ChildProcessError):
            self._running = False
            return False
