"""Health check route."""

import shutil

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    tmux_available: bool
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check server health and tmux availability."""
    from termweave import __version__

    tmux_available = shutil.which("tmux") is not None

    return HealthResponse(
        status="ok",
        tmux_available=tmux_available,
        version=__version__,
    )
