"""Session management routes."""

from fastapi import APIRouter, HTTPException, Request, status

from field_agent.models.auth import ErrorResponse
from field_agent.models.session import (
    AttachSessionResponse,
    CreateSessionRequest,
    SessionListResponse,
    SessionResponse,
)
from field_agent.server.dependencies import AuthDep, ProviderDep
from field_agent.services.tmux import TmuxError

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "",
    response_model=SessionListResponse,
)
async def list_sessions(
    _auth: AuthDep,
    provider: ProviderDep,
) -> SessionListResponse:
    """List all tmux sessions. Requires authentication."""
    try:
        sessions = await provider.list_sessions()

        return SessionListResponse(
            sessions=[
                SessionResponse(
                    id=s.id,
                    name=s.name,
                    server=s.server,
                    created_at=s.created_at,
                    attached=s.attached,
                    windows=s.windows,
                    width=s.width,
                    height=s.height,
                )
                for s in sessions
            ],
            total=len(sessions),
        )
    except TmuxError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid session name"},
        409: {"model": ErrorResponse, "description": "Session already exists"},
    },
)
async def create_session(
    _auth: AuthDep,
    provider: ProviderDep,
    body: CreateSessionRequest,
) -> SessionResponse:
    """Create a new tmux session. Requires authentication."""
    try:
        session = await provider.create_session(body.name)

        return SessionResponse(
            id=session.id,
            name=session.name,
            server=session.server,
            created_at=session.created_at,
            attached=session.attached,
            windows=session.windows,
            width=session.width,
            height=session.height,
        )
    except TmuxError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{session_id:path}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
async def get_session(
    session_id: str,
    _auth: AuthDep,
    provider: ProviderDep,
) -> SessionResponse:
    """Get a specific session by ID. Requires authentication."""
    try:
        session = await provider.get_session(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )

        return SessionResponse(
            id=session.id,
            name=session.name,
            server=session.server,
            created_at=session.created_at,
            attached=session.attached,
            windows=session.windows,
            width=session.width,
            height=session.height,
        )
    except TmuxError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{session_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
async def delete_session(
    session_id: str,
    _auth: AuthDep,
    provider: ProviderDep,
) -> None:
    """Kill a tmux session. Requires authentication."""
    try:
        await provider.kill_session(session_id)
    except TmuxError as e:
        if "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{session_id:path}/attach",
    response_model=AttachSessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
async def attach_session(
    request: Request,
    session_id: str,
    _auth: AuthDep,
    provider: ProviderDep,
) -> AttachSessionResponse:
    """Get WebSocket URL for attaching to a session. Requires authentication."""
    try:
        session = await provider.get_session(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )

        # Build WebSocket URL
        host = request.headers.get("host", "localhost:8080")
        scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_url = f"{scheme}://{host}/ws/terminal/{session_id}"

        return AttachSessionResponse(
            session_id=session_id,
            websocket_url=ws_url,
        )
    except TmuxError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
