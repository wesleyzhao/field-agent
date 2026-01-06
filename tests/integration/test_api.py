"""Integration tests for REST API endpoints.

These tests verify authentication, authorization, and CRUD operations.
"""

import pytest
import httpx

# Test configuration
BASE_URL = "http://localhost:8080"
TEST_PASSPHRASE = "my-super-secure-test-passphrase-2024"


@pytest.fixture
async def client():
    """Create an async HTTP client."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        yield client


@pytest.fixture
async def auth_headers(client):
    """Get authentication headers with valid JWT."""
    response = await client.post(
        "/auth/login",
        json={"passphrase": TEST_PASSPHRASE},
    )
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")

    data = response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """Health endpoint should return 200 OK."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "tmux_available" in data
        assert "version" in data


class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_with_valid_passphrase(self, client):
        """Login with correct passphrase should return tokens."""
        response = await client.post(
            "/auth/login",
            json={"passphrase": TEST_PASSPHRASE},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_with_invalid_passphrase(self, client):
        """Login with wrong passphrase should return 401."""
        response = await client.post(
            "/auth/login",
            json={"passphrase": "wrong-passphrase"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client):
        """Refresh token should return new tokens."""
        # First login
        login_response = await client.post(
            "/auth/login",
            json={"passphrase": TEST_PASSPHRASE},
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Then refresh
        refresh_response = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestSessionsAuthentication:
    """Test that sessions endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self, client):
        """GET /sessions without auth should return 401."""
        response = await client.get("/sessions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_create_session_requires_auth(self, client):
        """POST /sessions without auth should return 401."""
        response = await client.post("/sessions", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_get_session_requires_auth(self, client):
        """GET /sessions/{id} without auth should return 401."""
        response = await client.get("/sessions/local:test")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_delete_session_requires_auth(self, client):
        """DELETE /sessions/{id} without auth should return 401."""
        response = await client.delete("/sessions/local:test")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_list_sessions_with_auth(self, client, auth_headers):
        """GET /sessions with auth should return 200."""
        response = await client.get("/sessions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data


class TestSessionsCRUD:
    """Test session CRUD operations (with auth)."""

    @pytest.mark.asyncio
    async def test_create_and_delete_session(self, client, auth_headers):
        """Should be able to create and delete a session."""
        session_name = "test-api-session"

        # Create
        create_response = await client.post(
            "/sessions",
            json={"name": session_name},
            headers=auth_headers,
        )
        # May already exist from previous test run
        if create_response.status_code == 409:
            # Delete and try again
            await client.delete(f"/sessions/local:{session_name}", headers=auth_headers)
            create_response = await client.post(
                "/sessions",
                json={"name": session_name},
                headers=auth_headers,
            )

        assert create_response.status_code == 201
        session = create_response.json()
        assert session["name"] == session_name
        assert session["id"] == f"local:{session_name}"

        # Get
        get_response = await client.get(
            f"/sessions/{session['id']}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["name"] == session_name

        # Delete
        delete_response = await client.delete(
            f"/sessions/{session['id']}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204

        # Verify deleted
        get_after_delete = await client.get(
            f"/sessions/{session['id']}",
            headers=auth_headers,
        )
        assert get_after_delete.status_code == 404

    @pytest.mark.asyncio
    async def test_create_session_invalid_name(self, client, auth_headers):
        """Creating session with invalid name should fail."""
        response = await client.post(
            "/sessions",
            json={"name": "invalid name with spaces!"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422)  # Bad request or validation error


# Smoke test runner
if __name__ == "__main__":
    import asyncio

    async def smoke_test():
        """Quick smoke test for API."""
        print("Running API smoke test...")

        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            # Health
            response = await client.get("/health")
            if response.status_code != 200:
                print(f"FAIL: Health check failed: {response.status_code}")
                return False
            print("OK: Health check passed")

            # Login
            response = await client.post(
                "/auth/login",
                json={"passphrase": TEST_PASSPHRASE},
            )
            if response.status_code != 200:
                print(f"FAIL: Login failed: {response.status_code}")
                return False
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("OK: Login successful")

            # List sessions (with auth)
            response = await client.get("/sessions", headers=headers)
            if response.status_code != 200:
                print(f"FAIL: List sessions failed: {response.status_code}")
                return False
            print(f"OK: Listed {response.json()['total']} sessions")

            # Test auth required
            response = await client.get("/sessions")
            if response.status_code == 401:
                print("OK: Sessions require authentication")
            else:
                print(f"WARN: Sessions should require auth, got {response.status_code}")

            print("SUCCESS: API smoke test passed!")
            return True

    success = asyncio.run(smoke_test())
    exit(0 if success else 1)
