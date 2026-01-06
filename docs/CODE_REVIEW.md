# Code Review - field-agent MVP

**Reviewer**: Senior Engineer Review
**Date**: 2026-01-05
**Updated**: 2026-01-06
**Status**: P0 (Critical) fixes complete. P1/P3 remaining.

---

## Summary

The MVP is functional but has several architectural and security issues that should be addressed before production use. This document prioritizes issues by severity and provides a refactor plan.

---

## Critical Issues (P0) - ✅ FIXED

### 1. No Authentication on REST Endpoints - ✅ FIXED
**Location**: `server/routes/sessions.py`
**Issue**: Sessions API (list, create, delete, get) has NO authentication. Only WebSocket validates JWT.
**Risk**: Anyone can list/create/delete tmux sessions without logging in.
**Fix**: Added `AuthDep` dependency to all session route handlers.
**Verified**: Integration tests in `tests/integration/test_api.py::TestSessionsAuthentication` all pass.

### 2. Duplicate Provider Instances - ✅ FIXED
**Location**: `server/routes/sessions.py:18-26`, `server/websocket.py:17-26`
**Issue**: Both modules have separate `_provider` global and `get_provider()`. Creates duplicate `TmuxService` instances.
**Risk**: Inconsistent state, race conditions, wasted resources.
**Fix**: Created `server/dependencies.py` with shared `get_provider()`, `get_config()`, and type aliases (`ProviderDep`, `ConfigDep`, `AuthDep`, `JWTManagerDep`).

### 3. Config Loaded on Every Request - ✅ FIXED
**Location**: `server/routes/auth.py:83`, `server/websocket.py:39`
**Issue**: `Config.load()` called on every request, re-reads env vars and potentially YAML.
**Risk**: Performance overhead, unnecessary I/O.
**Fix**: Config is now cached in `dependencies.py` via global `_config` variable. All routes use `ConfigDep` or `get_config()` for cached access.

---

## High Priority Issues (P1)

### 4. Blocking I/O in Async Functions
**Location**: `providers/local.py:58-61`, `services/tmux.py` (all subprocess calls)
**Issue**: `subprocess.run()` blocks the event loop in async route handlers.
**Risk**: Poor concurrency, can block entire server during tmux operations.
**Fix**: Use `asyncio.create_subprocess_exec()` or `run_in_executor()`.

### 5. In-Memory Rate Limiting Won't Scale
**Location**: `server/routes/auth.py:17-19`
**Issue**: Rate limiting uses module-level dict, not shared across workers, no TTL cleanup.
**Risk**: Rate limiting ineffective with multiple workers, memory leak over time.
**Fix**: For MVP, add TTL cleanup. For production, use Redis.

### 6. Silent Exception Swallowing
**Location**: Multiple files
- `terminal_bridge.py:92-93, 109-110, 118-120, 127-128`
- `websocket.py:161-163, 185-186, 193-195, 218-219`
**Issue**: Exceptions caught and silently ignored with `pass`.
**Risk**: Bugs hidden, hard to debug failures.
**Fix**: Add logging, or at minimum log at DEBUG level.

### 7. No Dependency Injection Pattern
**Location**: All route modules
**Issue**: Routes instantiate their own dependencies instead of using FastAPI's DI.
**Risk**: Hard to test, hard to mock, duplicate instances.
**Fix**: Create proper FastAPI dependencies using `Depends()`.

---

## Medium Priority Issues (P2)

### 8. Duplicate SessionResponse Mapping
**Location**: `server/routes/sessions.py:39-53, 77-86, 118-127`
**Issue**: Same field mapping repeated 3+ times.
**Fix**: Add `Session.to_response()` method or use Pydantic's `model_validate()`.

### 9. Inconsistent Error Handling
**Location**: Various route handlers
**Issue**: Some catch `TmuxError` and convert to HTTP exceptions, others let it bubble.
**Fix**: Standardize with exception handlers or consistent try/catch pattern.

### 10. No Structured Logging
**Location**: Entire codebase
**Issue**: No logging statements. Only uvicorn access logs.
**Fix**: Add Python logging with structured format.

### 11. Missing Integration Tests - ✅ FIXED
**Location**: `tests/`
**Issue**: No tests for REST API endpoints (only WebSocket smoke test exists).
**Fix**: Created `tests/integration/test_api.py` with comprehensive tests for auth, sessions CRUD, and authentication requirements. Also fixed `tests/integration/test_websocket.py` to use proper auth.

---

## Low Priority Issues (P3)

### 12. pyproject.toml Placeholder Email
**Location**: `pyproject.toml:13`
**Issue**: Shows "wesley@example.com"
**Fix**: Update or remove.

### 13. Health Check Incomplete
**Location**: `server/routes/health.py`
**Issue**: Doesn't verify WebSocket capability or config validity.
**Fix**: Add more comprehensive health checks.

### 14. No HTTPS Warning
**Location**: `cli/main.py`, `server/app.py`
**Issue**: No warning when running HTTP in non-debug mode.
**Fix**: Add startup warning about HTTPS.

---

## Refactor Plan

### Phase 1: Security Fixes (P0)
1. Add authentication dependency to sessions routes
2. Create shared provider via dependency injection
3. Cache config at app startup

### Phase 2: Architecture Improvements (P1)
4. Convert blocking subprocess to async
5. Add logging throughout
6. Fix rate limiting with TTL cleanup

### Phase 3: Code Quality (P2)
7. Eliminate duplicate code
8. Add REST API integration tests
9. Standardize error handling

### Phase 4: Polish (P3)
10. Fix metadata
11. Improve health checks
12. Add startup warnings

---

## Testing Strategy

Each refactor will follow TDD:
1. Write failing test for the fix
2. Implement the fix
3. Verify test passes
4. Run full test suite
5. Manual smoke test

**Test Commands:**
```bash
# Unit tests
PYTHONPATH=. python3 -m pytest tests/unit/ -v

# Integration tests
PYTHONPATH=. python3 -m pytest tests/integration/ -v

# All tests with coverage
PYTHONPATH=. python3 -m pytest tests/ -v --cov=field-agent

# WebSocket smoke test
PYTHONPATH=. python3 tests/integration/test_websocket.py
```
