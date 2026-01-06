"""Authentication models."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request body for login endpoint."""

    passphrase: str = Field(..., min_length=1, description="The passphrase for authentication")


class TokenResponse(BaseModel):
    """Response body containing JWT tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshRequest(BaseModel):
    """Request body for token refresh endpoint."""

    refresh_token: str = Field(..., description="The refresh token to exchange")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error description")
