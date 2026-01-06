"""Integration tests for WebSocket terminal connection.

These tests verify the full WebSocket flow works end-to-end.
"""

import asyncio
import base64
import json

import pytest
import websockets
from websockets.exceptions import InvalidStatus

# Test configuration - uses a running server
SERVER_URL = "ws://localhost:8080"
HTTP_URL = "http://localhost:8080"


@pytest.fixture
def secret_key():
    """Test secret key matching server config."""
    return "super-secret-key-for-jwt-signing-at-least-32-chars"


@pytest.fixture
def passphrase():
    """Test passphrase matching server config."""
    return "my-super-secure-test-passphrase-2024"


@pytest.fixture
async def access_token(passphrase):
    """Get an access token from the server."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HTTP_URL}/auth/login",
            json={"passphrase": passphrase},
        )
        if response.status_code != 200:
            pytest.skip(f"Server not available or login failed: {response.status_code}")
        data = response.json()
        return data["access_token"]


@pytest.fixture
async def test_session(access_token):
    """Create a test session and clean up after."""
    import httpx

    session_name = "test-ws-session"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        # Create session
        response = await client.post(
            f"{HTTP_URL}/sessions",
            json={"name": session_name},
            headers=headers,
        )
        if response.status_code == 409:
            # Session already exists, delete and recreate
            await client.delete(f"{HTTP_URL}/sessions/local:{session_name}", headers=headers)
            response = await client.post(
                f"{HTTP_URL}/sessions",
                json={"name": session_name},
                headers=headers,
            )

        if response.status_code not in (200, 201):
            pytest.skip(f"Failed to create test session: {response.status_code}")

        session = response.json()
        yield session

        # Cleanup
        await client.delete(f"{HTTP_URL}/sessions/{session['id']}", headers=headers)


class TestWebSocketConnection:
    """Test WebSocket connection and authentication."""

    @pytest.mark.asyncio
    async def test_websocket_requires_token(self, test_session):
        """WebSocket connection without token should be rejected."""
        session_id = test_session["id"]
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}"

        with pytest.raises(InvalidStatus) as exc_info:
            async with websockets.connect(ws_url):
                pass

        # Should reject with 403 (forbidden) or 401 (unauthorized)
        assert exc_info.value.response.status_code in (4001, 403, 401)

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_token(self, test_session):
        """WebSocket connection with invalid token should be rejected."""
        session_id = test_session["id"]
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}?token=invalid-token"

        with pytest.raises(InvalidStatus) as exc_info:
            async with websockets.connect(ws_url):
                pass

        assert exc_info.value.response.status_code in (4001, 403, 401)

    @pytest.mark.asyncio
    async def test_websocket_connects_with_valid_token(self, test_session, access_token):
        """WebSocket connection with valid token should succeed."""
        session_id = test_session["id"]
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}?token={access_token}"

        async with websockets.connect(ws_url) as ws:
            # Connection successful - send a ping
            await ws.send(json.dumps({"type": "ping"}))

            # Should receive pong
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            assert data["type"] == "pong"

    @pytest.mark.asyncio
    async def test_websocket_receives_terminal_output(self, test_session, access_token):
        """WebSocket should receive terminal output."""
        session_id = test_session["id"]
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}?token={access_token}"

        async with websockets.connect(ws_url) as ws:
            # Send resize to ensure terminal is set up
            await ws.send(json.dumps({"type": "resize", "cols": 80, "rows": 24}))

            # Send a simple command (echo)
            command = "echo hello\n"
            encoded = base64.b64encode(command.encode()).decode()
            await ws.send(json.dumps({"type": "input", "data": encoded}))

            # Collect output for a short time
            output = b""
            try:
                for _ in range(10):
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    if isinstance(msg, bytes):
                        output += msg
                    elif isinstance(msg, str):
                        # Could be JSON control message
                        try:
                            data = json.loads(msg)
                            if data.get("type") == "error":
                                pytest.fail(f"Received error: {data.get('message')}")
                        except json.JSONDecodeError:
                            output += msg.encode()
            except asyncio.TimeoutError:
                pass

            # Should have received some output
            assert len(output) > 0, "Expected to receive terminal output"

    @pytest.mark.asyncio
    async def test_websocket_handles_resize(self, test_session, access_token):
        """WebSocket should handle resize messages."""
        session_id = test_session["id"]
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}?token={access_token}"

        async with websockets.connect(ws_url) as ws:
            # Send resize
            await ws.send(json.dumps({"type": "resize", "cols": 120, "rows": 40}))

            # Should not error - send ping to verify connection still works
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)

            # May receive terminal output or pong
            if isinstance(response, str):
                try:
                    data = json.loads(response)
                    if data.get("type") == "error":
                        pytest.fail(f"Resize caused error: {data.get('message')}")
                except json.JSONDecodeError:
                    pass


class TestWebSocketSessionNotFound:
    """Test WebSocket behavior for non-existent sessions."""

    @pytest.mark.asyncio
    async def test_websocket_nonexistent_session(self, access_token):
        """WebSocket to non-existent session should fail gracefully."""
        ws_url = f"{SERVER_URL}/ws/terminal/local:nonexistent-session-xyz?token={access_token}"

        async with websockets.connect(ws_url) as ws:
            # Should receive an error message
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            assert data["type"] == "error"
            assert "not found" in data["message"].lower()


# Run a quick smoke test when this file is executed directly
if __name__ == "__main__":
    import httpx

    async def smoke_test():
        """Quick smoke test for WebSocket functionality."""
        print("Running WebSocket smoke test...")

        # Check server is running
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{HTTP_URL}/health")
                if response.status_code != 200:
                    print(f"FAIL: Server health check failed: {response.status_code}")
                    return False
                print("OK: Server is running")
            except Exception as e:
                print(f"FAIL: Cannot connect to server: {e}")
                return False

            # Login
            response = await client.post(
                f"{HTTP_URL}/auth/login",
                json={"passphrase": "my-super-secure-test-passphrase-2024"},
            )
            if response.status_code != 200:
                print(f"FAIL: Login failed: {response.status_code}")
                return False
            token = response.json()["access_token"]
            print("OK: Login successful")

            # Get sessions
            response = await client.get(f"{HTTP_URL}/sessions")
            sessions = response.json()["sessions"]
            if not sessions:
                print("WARN: No sessions available for WebSocket test")
                return True

            session_id = sessions[0]["id"]
            print(f"OK: Using session {session_id}")

        # Test WebSocket
        ws_url = f"{SERVER_URL}/ws/terminal/{session_id}?token={token}"
        try:
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                await ws.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(ws.recv(), timeout=5)

                # Could be binary terminal output or JSON
                if isinstance(response, str):
                    try:
                        data = json.loads(response)
                        if data.get("type") == "pong":
                            print("OK: WebSocket ping/pong working")
                        elif data.get("type") == "error":
                            print(f"FAIL: WebSocket error: {data.get('message')}")
                            return False
                    except json.JSONDecodeError:
                        print("OK: Received terminal output")
                else:
                    print("OK: Received binary terminal output")

                print("SUCCESS: WebSocket connection working!")
                return True

        except InvalidStatus as e:
            print(f"FAIL: WebSocket connection rejected: {e.response.status_code}")
            return False
        except Exception as e:
            print(f"FAIL: WebSocket error: {e}")
            return False

    success = asyncio.run(smoke_test())
    exit(0 if success else 1)
