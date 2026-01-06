"""FastAPI dependencies for field-agent.

This module provides shared dependencies for route handlers using
FastAPI's dependency injection system.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from field_agent.auth import AuthError, JWTManager
from field_agent.config import Config, ConfigError
from field_agent.providers.local import LocalServerProvider

# Cached instances
_config: Config | None = None
_provider: LocalServerProvider | None = None


def get_config() -> Config:
    """Get cached configuration.

    The config is loaded once and cached for the lifetime of the application.
    """
    global _config
    if _config is None:
        try:
            _config = Config.load()
        except ConfigError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Configuration error: {e}",
            )
    return _config


def get_provider() -> LocalServerProvider:
    """Get shared provider instance.

    The provider is created once and shared across all route handlers.
    """
    global _provider
    if _provider is None:
        _provider = LocalServerProvider()
    return _provider


def get_jwt_manager(config: Annotated[Config, Depends(get_config)]) -> JWTManager:
    """Get JWT manager configured from app config."""
    return JWTManager(
        secret_key=config.secret_key,
        access_token_expire_seconds=config.access_token_expire_seconds,
        refresh_token_expire_seconds=config.refresh_token_expire_seconds,
    )


async def verify_token(
    authorization: Annotated[str | None, Header()] = None,
    jwt_manager: Annotated[JWTManager, Depends(get_jwt_manager)] = None,
) -> dict:
    """Verify JWT token from Authorization header.

    Args:
        authorization: The Authorization header value

    Returns:
        The decoded token payload

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        payload = jwt_manager.verify_access_token(token)
        return payload
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# Type aliases for use in route handlers
ConfigDep = Annotated[Config, Depends(get_config)]
ProviderDep = Annotated[LocalServerProvider, Depends(get_provider)]
JWTManagerDep = Annotated[JWTManager, Depends(get_jwt_manager)]
AuthDep = Annotated[dict, Depends(verify_token)]
