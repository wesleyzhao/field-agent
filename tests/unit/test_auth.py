"""Tests for field-agent.auth module."""

import time
from datetime import datetime, timedelta, timezone

import pytest

from field_agent.auth import JWTManager, PassphraseHasher, AuthError


class TestPassphraseHasher:
    """Test passphrase hashing functionality."""

    def test_hash_passphrase_returns_hash(self):
        """hash_passphrase should return a bcrypt hash."""
        hasher = PassphraseHasher()
        passphrase = "my-secure-passphrase-123!"
        hashed = hasher.hash_passphrase(passphrase)
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60

    def test_verify_passphrase_correct(self):
        """verify_passphrase should return True for correct passphrase."""
        hasher = PassphraseHasher()
        passphrase = "my-secure-passphrase-123!"
        hashed = hasher.hash_passphrase(passphrase)
        assert hasher.verify_passphrase(passphrase, hashed) is True

    def test_verify_passphrase_incorrect(self):
        """verify_passphrase should return False for incorrect passphrase."""
        hasher = PassphraseHasher()
        passphrase = "my-secure-passphrase-123!"
        hashed = hasher.hash_passphrase(passphrase)
        assert hasher.verify_passphrase("wrong-passphrase", hashed) is False

    def test_different_hashes_for_same_passphrase(self):
        """Hashing the same passphrase twice should produce different hashes (salt)."""
        hasher = PassphraseHasher()
        passphrase = "my-secure-passphrase-123!"
        hash1 = hasher.hash_passphrase(passphrase)
        hash2 = hasher.hash_passphrase(passphrase)
        assert hash1 != hash2
        # But both should verify correctly
        assert hasher.verify_passphrase(passphrase, hash1) is True
        assert hasher.verify_passphrase(passphrase, hash2) is True

    def test_hash_with_custom_rounds(self):
        """Should support custom bcrypt rounds."""
        hasher = PassphraseHasher(rounds=10)
        passphrase = "test-passphrase"
        hashed = hasher.hash_passphrase(passphrase)
        assert "$10$" in hashed

    def test_default_rounds_is_12(self):
        """Default bcrypt rounds should be 12."""
        hasher = PassphraseHasher()
        passphrase = "test-passphrase"
        hashed = hasher.hash_passphrase(passphrase)
        assert "$12$" in hashed


class TestJWTManager:
    """Test JWT token functionality."""

    @pytest.fixture
    def jwt_manager(self):
        """Create a JWTManager for testing."""
        return JWTManager(
            secret_key="test-secret-key-that-is-at-least-32-chars-long",
            access_token_expire_seconds=900,  # 15 minutes
            refresh_token_expire_seconds=604800,  # 7 days
        )

    def test_create_access_token(self, jwt_manager):
        """create_access_token should return a valid JWT string."""
        token = jwt_manager.create_access_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # JWT format: header.payload.signature
        assert token.count(".") == 2

    def test_create_refresh_token(self, jwt_manager):
        """create_refresh_token should return a valid JWT string."""
        token = jwt_manager.create_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_verify_access_token_valid(self, jwt_manager):
        """verify_access_token should return payload for valid token."""
        token = jwt_manager.create_access_token()
        payload = jwt_manager.verify_access_token(token)
        assert payload is not None
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "jti" in payload

    def test_verify_refresh_token_valid(self, jwt_manager):
        """verify_refresh_token should return payload for valid token."""
        token = jwt_manager.create_refresh_token()
        payload = jwt_manager.verify_refresh_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "jti" in payload

    def test_verify_access_token_invalid_signature(self, jwt_manager):
        """verify_access_token should raise AuthError for invalid signature."""
        token = jwt_manager.create_access_token()
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthError, match="Invalid token"):
            jwt_manager.verify_access_token(tampered)

    def test_verify_access_token_expired(self):
        """verify_access_token should raise AuthError for expired token."""
        manager = JWTManager(
            secret_key="test-secret-key-that-is-at-least-32-chars-long",
            access_token_expire_seconds=1,  # Expire after 1 second
            refresh_token_expire_seconds=1,
        )
        token = manager.create_access_token()
        time.sleep(2.5)  # Wait for token to expire (with buffer for system time variance)
        with pytest.raises(AuthError, match="Token expired"):
            manager.verify_access_token(token)

    def test_verify_access_token_wrong_type(self, jwt_manager):
        """verify_access_token should raise AuthError for refresh token."""
        refresh_token = jwt_manager.create_refresh_token()
        with pytest.raises(AuthError, match="Invalid token type"):
            jwt_manager.verify_access_token(refresh_token)

    def test_verify_refresh_token_wrong_type(self, jwt_manager):
        """verify_refresh_token should raise AuthError for access token."""
        access_token = jwt_manager.create_access_token()
        with pytest.raises(AuthError, match="Invalid token type"):
            jwt_manager.verify_refresh_token(access_token)

    def test_token_has_unique_jti(self, jwt_manager):
        """Each token should have a unique jti (JWT ID)."""
        token1 = jwt_manager.create_access_token()
        token2 = jwt_manager.create_access_token()

        payload1 = jwt_manager.verify_access_token(token1)
        payload2 = jwt_manager.verify_access_token(token2)

        assert payload1["jti"] != payload2["jti"]

    def test_access_token_expiry(self, jwt_manager):
        """Access token should have correct expiry time."""
        now = datetime.now(timezone.utc)
        token = jwt_manager.create_access_token()
        payload = jwt_manager.verify_access_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = now + timedelta(seconds=900)

        # Allow 5 seconds tolerance
        assert abs((exp - expected_exp).total_seconds()) < 5

    def test_refresh_token_expiry(self, jwt_manager):
        """Refresh token should have correct expiry time."""
        now = datetime.now(timezone.utc)
        token = jwt_manager.create_refresh_token()
        payload = jwt_manager.verify_refresh_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = now + timedelta(seconds=604800)

        # Allow 5 seconds tolerance
        assert abs((exp - expected_exp).total_seconds()) < 5

    def test_malformed_token_raises_error(self, jwt_manager):
        """Malformed token should raise AuthError."""
        with pytest.raises(AuthError, match="Invalid token"):
            jwt_manager.verify_access_token("not.a.valid.token")

    def test_empty_token_raises_error(self, jwt_manager):
        """Empty token should raise AuthError."""
        with pytest.raises(AuthError, match="Invalid token"):
            jwt_manager.verify_access_token("")


class TestAuthIntegration:
    """Integration tests for auth flow."""

    def test_full_auth_flow(self):
        """Test complete authentication flow."""
        # Setup
        hasher = PassphraseHasher()
        passphrase = "my-secure-passphrase-for-testing-123!"
        stored_hash = hasher.hash_passphrase(passphrase)

        jwt_manager = JWTManager(
            secret_key="test-secret-key-that-is-at-least-32-chars-long",
            access_token_expire_seconds=900,
            refresh_token_expire_seconds=604800,
        )

        # Verify passphrase
        assert hasher.verify_passphrase(passphrase, stored_hash) is True

        # Generate tokens
        access_token = jwt_manager.create_access_token()
        refresh_token = jwt_manager.create_refresh_token()

        # Verify tokens
        access_payload = jwt_manager.verify_access_token(access_token)
        refresh_payload = jwt_manager.verify_refresh_token(refresh_token)

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
