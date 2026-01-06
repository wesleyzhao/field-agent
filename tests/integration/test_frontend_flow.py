"""Integration tests for frontend user flow.

These tests verify the complete user flow works end-to-end,
simulating what the browser JavaScript would do.
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


class TestFrontendUserFlow:
    """Test the complete frontend user flow."""

    @pytest.mark.asyncio
    async def test_complete_user_flow(self, client):
        """Test: login -> load sessions -> create session -> delete session.

        This simulates exactly what the frontend JavaScript does.
        """
        # Step 1: Login (simulates auth.js login())
        login_response = await client.post(
            "/auth/login",
            json={"passphrase": TEST_PASSPHRASE},
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

        tokens = login_response.json()
        assert "access_token" in tokens
        access_token = tokens["access_token"]

        # Create auth headers (simulates what app.js should do)
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Step 2: Load sessions (simulates app.js _loadSessions())
        sessions_response = await client.get("/sessions", headers=auth_headers)
        assert sessions_response.status_code == 200, f"Load sessions failed: {sessions_response.text}"

        sessions_data = sessions_response.json()
        assert "sessions" in sessions_data
        assert "total" in sessions_data

        # Step 3: Create a session (simulates app.js _createSession())
        create_response = await client.post(
            "/sessions",
            json={"name": "test-frontend-flow"},
            headers=auth_headers,
        )
        # May be 201 (created) or 409 (already exists)
        if create_response.status_code == 409:
            # Clean up and try again
            await client.delete("/sessions/local:test-frontend-flow", headers=auth_headers)
            create_response = await client.post(
                "/sessions",
                json={"name": "test-frontend-flow"},
                headers=auth_headers,
            )

        assert create_response.status_code == 201, f"Create session failed: {create_response.text}"
        created_session = create_response.json()
        assert created_session["name"] == "test-frontend-flow"

        # Step 4: Load sessions again to verify session appears
        sessions_response = await client.get("/sessions", headers=auth_headers)
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()["sessions"]
        session_names = [s["name"] for s in sessions]
        assert "test-frontend-flow" in session_names

        # Step 5: Delete the session (simulates app.js _deleteSession())
        delete_response = await client.delete(
            f"/sessions/{created_session['id']}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204, f"Delete failed: {delete_response.text}"

        # Step 6: Verify session is gone
        sessions_response = await client.get("/sessions", headers=auth_headers)
        sessions = sessions_response.json()["sessions"]
        session_names = [s["name"] for s in sessions]
        assert "test-frontend-flow" not in session_names

    @pytest.mark.asyncio
    async def test_sessions_require_auth_header(self, client):
        """Test that sessions endpoint fails without auth header.

        This catches the bug where frontend forgot to send Authorization header.
        """
        # Without auth header should fail
        response = await client.get("/sessions")
        assert response.status_code == 401, "Sessions should require auth header"

        # With invalid token should fail
        response = await client.get(
            "/sessions",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401, "Invalid token should be rejected"

    @pytest.mark.asyncio
    async def test_create_session_requires_auth_header(self, client):
        """Test that create session fails without auth header."""
        response = await client.post(
            "/sessions",
            json={"name": "should-fail"},
        )
        assert response.status_code == 401, "Create session should require auth"

    @pytest.mark.asyncio
    async def test_delete_session_requires_auth_header(self, client):
        """Test that delete session fails without auth header."""
        response = await client.delete("/sessions/local:any-session")
        assert response.status_code == 401, "Delete session should require auth"
