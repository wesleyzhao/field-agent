"""Session models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Response model for a session."""

    id: str = Field(..., description="Session ID (format: server:name)")
    name: str = Field(..., description="Session name")
    server: str = Field(..., description="Server identifier")
    created_at: datetime = Field(..., description="When the session was created")
    attached: bool = Field(..., description="Whether the session is attached")
    windows: int = Field(default=1, description="Number of windows")
    width: Optional[int] = Field(default=None, description="Terminal width")
    height: Optional[int] = Field(default=None, description="Terminal height")


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: list[SessionResponse]
    total: int


class CreateSessionRequest(BaseModel):
    """Request model for creating a session."""

    name: Optional[str] = Field(
        default=None,
        description="Optional session name. Auto-generated if not provided.",
        pattern=r"^[a-zA-Z0-9_-]+$",
        min_length=1,
        max_length=64,
    )


class AttachSessionResponse(BaseModel):
    """Response model for session attach."""

    session_id: str
    websocket_url: str = Field(..., description="WebSocket URL for terminal connection")
