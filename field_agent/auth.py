"""Authentication module for field-agent.

Provides passphrase hashing (bcrypt) and JWT token management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.hash import bcrypt


class AuthError(Exception):
    """Authentication error."""

    pass


class PassphraseHasher:
    """Handles passphrase hashing and verification using bcrypt."""

    def __init__(self, rounds: int = 12):
        """Initialize hasher with bcrypt rounds.

        Args:
            rounds: Number of bcrypt rounds (default 12, higher = slower but more secure)
        """
        self.rounds = rounds

    def hash_passphrase(self, passphrase: str) -> str:
        """Hash a passphrase using bcrypt.

        Args:
            passphrase: The plaintext passphrase to hash

        Returns:
            The bcrypt hash string
        """
        return bcrypt.using(rounds=self.rounds).hash(passphrase)

    def verify_passphrase(self, passphrase: str, hashed: str) -> bool:
        """Verify a passphrase against a stored hash.

        Args:
            passphrase: The plaintext passphrase to verify
            hashed: The stored bcrypt hash

        Returns:
            True if the passphrase matches, False otherwise
        """
        try:
            return bcrypt.verify(passphrase, hashed)
        except Exception:
            return False


class JWTManager:
    """Manages JWT token creation and verification."""

    def __init__(
        self,
        secret_key: str,
        access_token_expire_seconds: int = 900,  # 15 minutes
        refresh_token_expire_seconds: int = 604800,  # 7 days
        algorithm: str = "HS256",
    ):
        """Initialize JWT manager.

        Args:
            secret_key: Secret key for signing tokens (min 32 chars recommended)
            access_token_expire_seconds: Access token expiry in seconds
            refresh_token_expire_seconds: Refresh token expiry in seconds
            algorithm: JWT signing algorithm (default HS256)
        """
        self.secret_key = secret_key
        self.access_token_expire_seconds = access_token_expire_seconds
        self.refresh_token_expire_seconds = refresh_token_expire_seconds
        self.algorithm = algorithm

    def create_access_token(self, additional_claims: dict[str, Any] | None = None) -> str:
        """Create a new access token.

        Args:
            additional_claims: Optional additional claims to include

        Returns:
            The encoded JWT string
        """
        return self._create_token(
            token_type="access",
            expire_seconds=self.access_token_expire_seconds,
            additional_claims=additional_claims,
        )

    def create_refresh_token(self, additional_claims: dict[str, Any] | None = None) -> str:
        """Create a new refresh token.

        Args:
            additional_claims: Optional additional claims to include

        Returns:
            The encoded JWT string
        """
        return self._create_token(
            token_type="refresh",
            expire_seconds=self.refresh_token_expire_seconds,
            additional_claims=additional_claims,
        )

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify an access token and return its payload.

        Args:
            token: The JWT string to verify

        Returns:
            The decoded token payload

        Raises:
            AuthError: If token is invalid, expired, or wrong type
        """
        payload = self._verify_token(token)
        if payload.get("type") != "access":
            raise AuthError("Invalid token type: expected access token")
        return payload

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """Verify a refresh token and return its payload.

        Args:
            token: The JWT string to verify

        Returns:
            The decoded token payload

        Raises:
            AuthError: If token is invalid, expired, or wrong type
        """
        payload = self._verify_token(token)
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type: expected refresh token")
        return payload

    def _create_token(
        self,
        token_type: str,
        expire_seconds: int,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a JWT token.

        Args:
            token_type: Type of token ("access" or "refresh")
            expire_seconds: Token expiry in seconds
            additional_claims: Optional additional claims

        Returns:
            The encoded JWT string
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(seconds=expire_seconds)

        payload = {
            "type": token_type,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def _verify_token(self, token: str) -> dict[str, Any]:
        """Verify a JWT token and return its payload.

        Args:
            token: The JWT string to verify

        Returns:
            The decoded token payload

        Raises:
            AuthError: If token is invalid or expired
        """
        if not token:
            raise AuthError("Invalid token: empty token")

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"require": ["exp", "iat", "jti", "type"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.InvalidTokenError as e:
            raise AuthError(f"Invalid token: {e}")
