"""WebSocket endpoint for terminal connections."""

import asyncio
import base64
import json
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from field_agent.auth import AuthError
from field_agent.server.dependencies import get_config, get_jwt_manager, get_provider
from field_agent.services.terminal_bridge import TerminalBridge

router = APIRouter()


def validate_token(token: str) -> bool:
    """Validate a JWT token using cached config.

    Args:
        token: The JWT token to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        config = get_config()
        jwt_manager = get_jwt_manager(config)
        jwt_manager.verify_access_token(token)
        return True
    except (AuthError, Exception):
        return False


@router.websocket("/ws/terminal/{session_id:path}")
async def terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(default=None),
):
    """WebSocket endpoint for terminal attachment.

    Protocol:
    - Client sends text frames with JSON control messages
    - Server sends binary frames with terminal output
    - Control messages:
      - {"type": "input", "data": "<base64 encoded input>"}
      - {"type": "resize", "cols": 80, "rows": 24}
      - {"type": "ping"}
    - Server messages:
      - Binary: raw terminal output
      - {"type": "pong"}
      - {"type": "error", "message": "..."}
      - {"type": "closed", "reason": "..."}
    """
    # Validate token
    if not token or not validate_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Accept the connection
    await websocket.accept()

    # Verify session exists
    provider = get_provider()
    session = await provider.get_session(session_id)
    if session is None:
        await websocket.send_json({"type": "error", "message": f"Session not found: {session_id}"})
        await websocket.close(code=4004, reason="Session not found")
        return

    # Create terminal bridge
    bridge = TerminalBridge(provider, session_id)

    try:
        # Start the PTY process
        await bridge.start()

        # Set initial terminal size
        bridge.resize(80, 24)

        # Handle bidirectional communication
        await _handle_terminal_io(websocket, bridge)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await bridge.close()


async def _handle_terminal_io(websocket: WebSocket, bridge: TerminalBridge) -> None:
    """Handle bidirectional I/O between WebSocket and PTY.

    Args:
        websocket: The WebSocket connection
        bridge: The terminal bridge
    """
    # Create tasks for reading from PTY and WebSocket
    read_pty_task = asyncio.create_task(_read_pty_loop(websocket, bridge))
    read_ws_task = asyncio.create_task(_read_websocket_loop(websocket, bridge))

    try:
        # Wait for either task to complete (or fail)
        done, pending = await asyncio.wait(
            [read_pty_task, read_ws_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Check for exceptions
        for task in done:
            if task.exception():
                raise task.exception()

    except asyncio.CancelledError:
        pass


async def _read_pty_loop(websocket: WebSocket, bridge: TerminalBridge) -> None:
    """Read from PTY and send to WebSocket.

    Args:
        websocket: The WebSocket connection
        bridge: The terminal bridge
    """
    while bridge.is_running:
        try:
            data = await bridge.read_output()
            if data:
                await websocket.send_bytes(data)
            else:
                # Small delay to prevent busy loop
                await asyncio.sleep(0.01)
        except Exception:
            break


async def _read_websocket_loop(websocket: WebSocket, bridge: TerminalBridge) -> None:
    """Read from WebSocket and handle messages.

    Args:
        websocket: The WebSocket connection
        bridge: The terminal bridge
    """
    while bridge.is_running:
        try:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "text" in message:
                # JSON control message
                try:
                    data = json.loads(message["text"])
                    await _handle_control_message(websocket, bridge, data)
                except json.JSONDecodeError:
                    pass

            elif "bytes" in message:
                # Raw input data
                await bridge.write_input(message["bytes"])

        except WebSocketDisconnect:
            break
        except Exception:
            break


async def _handle_control_message(
    websocket: WebSocket,
    bridge: TerminalBridge,
    data: dict,
) -> None:
    """Handle a control message from the client.

    Args:
        websocket: The WebSocket connection
        bridge: The terminal bridge
        data: The parsed JSON message
    """
    msg_type = data.get("type")

    if msg_type == "input":
        # Base64-encoded input
        input_data = data.get("data", "")
        try:
            decoded = base64.b64decode(input_data)
            await bridge.write_input(decoded)
        except Exception:
            pass

    elif msg_type == "resize":
        # Terminal resize
        cols = data.get("cols", 80)
        rows = data.get("rows", 24)
        bridge.resize(cols, rows)

    elif msg_type == "ping":
        # Respond with pong
        await websocket.send_json({"type": "pong"})
