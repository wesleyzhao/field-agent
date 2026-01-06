"""Local server provider for managing tmux sessions on the local machine."""

from typing import Optional

from termweave.providers.base import ServerProvider, Session
from termweave.services.tmux import TmuxService, TmuxSession


class LocalServerProvider(ServerProvider):
    """Provider for managing local tmux sessions.

    This is the default provider for MVP, managing sessions
    on the same machine where termweave is running.
    """

    def __init__(self, server_name: str = "local"):
        """Initialize the local provider.

        Args:
            server_name: Name identifier for this server
        """
        self._name = server_name
        self._tmux = TmuxService()

    @property
    def name(self) -> str:
        """Unique identifier for this server."""
        return self._name

    @property
    def is_connected(self) -> bool:
        """Always connected for local server."""
        return True

    def _tmux_to_session(self, tmux_session: TmuxSession) -> Session:
        """Convert TmuxSession to Session."""
        return Session(
            id=f"{self._name}:{tmux_session.name}",
            name=tmux_session.name,
            server=self._name,
            created_at=tmux_session.created,
            attached=tmux_session.attached,
            windows=tmux_session.windows,
            width=tmux_session.width,
            height=tmux_session.height,
        )

    def _parse_session_id(self, session_id: str) -> str:
        """Extract session name from session ID.

        Session ID format: {server}:{session_name}
        """
        if ":" in session_id:
            _, name = session_id.split(":", 1)
            return name
        return session_id

    async def list_sessions(self) -> list[Session]:
        """List all tmux sessions."""
        tmux_sessions = self._tmux.list_sessions()
        return [self._tmux_to_session(s) for s in tmux_sessions]

    async def create_session(self, name: Optional[str] = None) -> Session:
        """Create a new tmux session."""
        tmux_session = self._tmux.create_session(name)
        return self._tmux_to_session(tmux_session)

    async def kill_session(self, session_id: str) -> bool:
        """Kill a session by ID."""
        name = self._parse_session_id(session_id)
        return self._tmux.kill_session(name)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a specific session by ID."""
        name = self._parse_session_id(session_id)
        tmux_session = self._tmux.get_session(name)
        if tmux_session:
            return self._tmux_to_session(tmux_session)
        return None

    async def get_attach_command(self, session_id: str) -> list[str]:
        """Get the command to attach to a session.

        Returns:
            Command list for tmux attach
        """
        name = self._parse_session_id(session_id)
        return ["tmux", "attach-session", "-t", name]
