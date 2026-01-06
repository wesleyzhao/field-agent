"""tmux session management service."""

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class TmuxError(Exception):
    """Error from tmux operations."""

    pass


@dataclass
class TmuxSession:
    """Represents a tmux session."""

    name: str
    created: datetime
    attached: bool
    windows: int
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def id(self) -> str:
        """Session ID (same as name for local sessions)."""
        return self.name


class TmuxService:
    """Service for managing tmux sessions."""

    def __init__(self):
        """Initialize the tmux service."""
        self._verify_tmux_available()

    def _verify_tmux_available(self) -> None:
        """Verify tmux is installed and accessible."""
        try:
            result = subprocess.run(
                ["tmux", "-V"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise TmuxError("tmux is not accessible")
        except FileNotFoundError:
            raise TmuxError("tmux is not installed")
        except subprocess.TimeoutExpired:
            raise TmuxError("tmux command timed out")

    def list_sessions(self) -> list[TmuxSession]:
        """List all tmux sessions.

        Returns:
            List of TmuxSession objects
        """
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "list-sessions",
                    "-F",
                    "#{session_name}|#{session_created}|#{session_attached}|#{session_windows}|#{session_width}|#{session_height}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                # No sessions is not an error
                if "no server running" in result.stderr or "no sessions" in result.stderr.lower():
                    return []
                raise TmuxError(f"Failed to list sessions: {result.stderr}")

            sessions = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 4:
                    name = parts[0]
                    created_ts = int(parts[1])
                    attached = parts[2] == "1"
                    windows = int(parts[3])
                    width = int(parts[4]) if len(parts) > 4 and parts[4] else None
                    height = int(parts[5]) if len(parts) > 5 and parts[5] else None

                    sessions.append(
                        TmuxSession(
                            name=name,
                            created=datetime.fromtimestamp(created_ts),
                            attached=attached,
                            windows=windows,
                            width=width,
                            height=height,
                        )
                    )

            return sessions

        except subprocess.TimeoutExpired:
            raise TmuxError("tmux list-sessions timed out")
        except Exception as e:
            if isinstance(e, TmuxError):
                raise
            raise TmuxError(f"Error listing sessions: {e}")

    def session_exists(self, name: str) -> bool:
        """Check if a session exists.

        Args:
            name: Session name to check

        Returns:
            True if session exists
        """
        result = subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0

    def create_session(self, name: Optional[str] = None) -> TmuxSession:
        """Create a new tmux session.

        Args:
            name: Optional session name. If not provided, a unique name is generated.

        Returns:
            The created TmuxSession

        Raises:
            TmuxError: If session creation fails
        """
        if name is None:
            name = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Validate name
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise TmuxError(f"Invalid session name: {name}. Use only letters, numbers, - and _")

        if self.session_exists(name):
            raise TmuxError(f"Session '{name}' already exists")

        try:
            result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise TmuxError(f"Failed to create session: {result.stderr}")

            # Fetch the created session
            sessions = self.list_sessions()
            for session in sessions:
                if session.name == name:
                    return session

            raise TmuxError(f"Session '{name}' was created but not found in list")

        except subprocess.TimeoutExpired:
            raise TmuxError("tmux new-session timed out")

    def kill_session(self, name: str) -> bool:
        """Kill a tmux session.

        Args:
            name: Session name to kill

        Returns:
            True if session was killed

        Raises:
            TmuxError: If session doesn't exist or kill fails
        """
        if not self.session_exists(name):
            raise TmuxError(f"Session '{name}' does not exist")

        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise TmuxError(f"Failed to kill session: {result.stderr}")

            return True

        except subprocess.TimeoutExpired:
            raise TmuxError("tmux kill-session timed out")

    def get_session(self, name: str) -> Optional[TmuxSession]:
        """Get a specific session by name.

        Args:
            name: Session name

        Returns:
            TmuxSession if found, None otherwise
        """
        sessions = self.list_sessions()
        for session in sessions:
            if session.name == name:
                return session
        return None
