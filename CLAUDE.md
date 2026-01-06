# CLAUDE.md - Developer Guide

This file provides guidance for Claude Code and other AI assistants working on this codebase.

## Quick Start for Development

```bash
cd ~/termweave

# Install in development mode
pip install -e ".[dev]"

# Generate credentials for testing
termweave generate-secret
termweave hash-passphrase

# Set environment variables
export TERMWEAVE_SECRET_KEY="your-generated-key"
export TERMWEAVE_PASSPHRASE_HASH="your-generated-hash"

# Run the server
termweave serve --reload

# Or run directly with uvicorn
PYTHONPATH=. python3 -m uvicorn termweave.server.app:app --host 0.0.0.0 --port 8080 --reload
```

## Running Tests

```bash
# All tests
pytest

# With verbose output
pytest -v

# Specific test file
pytest tests/unit/test_auth.py -v

# Integration tests (requires running server)
pytest tests/integration/ -v

# With coverage
pytest --cov=termweave tests/
```

**Test passphrase for integration tests:** `my-super-secure-test-passphrase-2024`

## Project Architecture

```
termweave/
├── termweave/              # Main package
│   ├── __init__.py         # Version info
│   ├── config.py           # Configuration (env vars + YAML)
│   ├── auth.py             # PassphraseHasher + JWTManager
│   │
│   ├── cli/
│   │   └── main.py         # Click CLI commands
│   │
│   ├── server/
│   │   ├── app.py          # FastAPI application factory
│   │   ├── dependencies.py # Shared DI (config, provider, auth)
│   │   ├── websocket.py    # WebSocket terminal endpoint
│   │   └── routes/
│   │       ├── auth.py     # POST /auth/login, /auth/refresh
│   │       ├── sessions.py # CRUD /sessions
│   │       └── health.py   # GET /health
│   │
│   ├── services/
│   │   ├── tmux.py         # TmuxService - subprocess wrapper
│   │   └── terminal_bridge.py  # PTY <-> WebSocket bridge
│   │
│   ├── providers/
│   │   ├── base.py         # Abstract ServerProvider
│   │   └── local.py        # LocalServerProvider (tmux on localhost)
│   │
│   └── models/
│       ├── auth.py         # Pydantic models for auth
│       └── session.py      # Pydantic models for sessions
│
├── static/                 # Frontend (no build step)
│   ├── index.html
│   ├── css/style.css       # Mobile-first, dark theme
│   └── js/
│       ├── app.js          # Main application logic
│       ├── auth.js         # Token management
│       └── terminal.js     # xterm.js wrapper
│
└── tests/
    ├── conftest.py         # Shared fixtures
    ├── unit/               # Unit tests (no server needed)
    └── integration/        # Integration tests (need running server)
```

## Key Design Patterns

### Dependency Injection
All routes use FastAPI's DI via `server/dependencies.py`:
- `ConfigDep` - Cached configuration
- `ProviderDep` - Shared tmux provider
- `AuthDep` - JWT token verification
- `JWTManagerDep` - JWT token creation

### Provider Abstraction
`ServerProvider` interface allows future multi-server support:
- `LocalServerProvider` - Current implementation (localhost tmux)
- Future: `SSHServerProvider`, `GCPServerProvider`

Session IDs encode server: `{server}:{session_name}` (e.g., `local:my-session`)

### WebSocket Protocol
```
Client → Server (JSON):  {"type": "input", "data": "<base64>"}
Client → Server (JSON):  {"type": "resize", "cols": 80, "rows": 24}
Client → Server (JSON):  {"type": "ping"}
Server → Client (binary): <raw terminal output>
Server → Client (JSON):  {"type": "pong"}
Server → Client (JSON):  {"type": "error", "message": "..."}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TERMWEAVE_SECRET_KEY` | Yes | JWT signing key (min 32 chars) |
| `TERMWEAVE_PASSPHRASE_HASH` | Yes | bcrypt hash of login passphrase |
| `TERMWEAVE_HOST` | No | Server host (default: 0.0.0.0) |
| `TERMWEAVE_PORT` | No | Server port (default: 8080) |
| `TERMWEAVE_DEBUG` | No | Enable debug mode |

## Common Tasks

### Add a new API endpoint
1. Create route in `server/routes/`
2. Add router to `server/app.py`
3. Add Pydantic models if needed
4. Add tests in `tests/integration/`

### Add a new provider
1. Subclass `ServerProvider` in `providers/`
2. Implement all abstract methods
3. Add tests in `tests/unit/`

### Modify authentication
1. Update `auth.py` for token logic
2. Update `server/dependencies.py` for verification
3. Update `server/routes/auth.py` for endpoints
4. Add tests in `tests/unit/test_auth.py`

## Known Issues / TODO

See `docs/CODE_REVIEW.md` for the full list. Key items:
- P1: Rate limiting is in-memory only (resets on restart)
- P1: Subprocess calls are blocking (should be async)
- P3: No HTTPS warning in production mode
