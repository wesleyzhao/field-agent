"""Authentication routes."""

from fastapi import APIRouter, HTTPException, Request, status

from field_agent.auth import AuthError, PassphraseHasher
from field_agent.models.auth import (
    ErrorResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from field_agent.server.dependencies import ConfigDep, JWTManagerDep

router = APIRouter(prefix="/auth", tags=["auth"])

# Rate limiting state (simple in-memory, would use Redis in production)
_login_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 60


def _check_rate_limit(client_ip: str) -> None:
    """Check if client has exceeded rate limit.

    Raises:
        HTTPException: If rate limit exceeded
    """
    import time

    now = time.time()
    attempts = _login_attempts.get(client_ip, [])

    # Remove old attempts outside window
    attempts = [t for t in attempts if now - t < WINDOW_SECONDS]
    _login_attempts[client_ip] = attempts

    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {WINDOW_SECONDS} seconds.",
        )


def _record_attempt(client_ip: str) -> None:
    """Record a login attempt."""
    import time

    if client_ip not in _login_attempts:
        _login_attempts[client_ip] = []
    _login_attempts[client_ip].append(time.time())


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid passphrase"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def login(
    request: Request,
    body: LoginRequest,
    config: ConfigDep,
    jwt_manager: JWTManagerDep,
) -> TokenResponse:
    """Authenticate with passphrase and receive JWT tokens.

    Rate limited to 5 attempts per minute per IP.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    _check_rate_limit(client_ip)
    _record_attempt(client_ip)

    # Verify passphrase
    if not config.passphrase_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured (no passphrase hash set)",
        )

    hasher = PassphraseHasher()
    if not hasher.verify_passphrase(body.passphrase, config.passphrase_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passphrase",
        )

    # Generate tokens
    access_token = jwt_manager.create_access_token()
    refresh_token = jwt_manager.create_refresh_token()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=config.access_token_expire_seconds,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    body: RefreshRequest,
    config: ConfigDep,
    jwt_manager: JWTManagerDep,
) -> TokenResponse:
    """Exchange a refresh token for new access and refresh tokens."""
    try:
        # Verify refresh token
        jwt_manager.verify_refresh_token(body.refresh_token)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Generate new tokens
    access_token = jwt_manager.create_access_token()
    refresh_token = jwt_manager.create_refresh_token()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=config.access_token_expire_seconds,
    )
