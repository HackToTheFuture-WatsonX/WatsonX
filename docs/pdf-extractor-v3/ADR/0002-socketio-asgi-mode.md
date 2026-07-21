# ADR 0002 — Socket.IO `async_mode="asgi"` with thread-safe emit

- **Status:** Accepted
- **Date:** 2026-02-19
- **Deciders:** V3 core team

## Context

Early V3 configured the Socket.IO server as:

```python
sio = socketio.Server(async_mode="threading")
```

Rationale at the time: worker threads (sync/scan/extract) could call `sio.emit()` directly, matching V2's synchronous Tkinter model.

Two problems emerged:

1. **Events silently dropped.** Under `async_mode="threading"` wrapped inside a `socketio.ASGIApp` served by uvicorn, `emit()` calls made from worker threads never reached connected clients. No error was raised, no log line was written — the UI just missed live progress.
2. **Latency.** When events did arrive (during matching-thread edge cases), they queued behind the request handler.

The uvicorn event loop is asyncio; `socketio.AsyncServer` requires an ASGI-compatible mode; `sio.emit()` in `AsyncServer` is a coroutine that must be scheduled onto that loop.

## Decision

Switch to `AsyncServer` and route every worker-thread emit through a thread-safe helper:

```python
# backend/main.py
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
)

@_fastapi.on_event("startup")
async def _capture_loop():
    events.configure(sio, asyncio.get_running_loop())
```

```python
# backend/events.py
def emit(event: str, data) -> None:
    if _sio is None or _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_sio.emit(event, data), _loop)
```

Worker threads call `events.emit(...)`. Never `sio.emit(...)` directly.

## Consequences

**Positive**
- Every emit reaches the client, unconditionally.
- Emits from the main loop (rare — used in health/response paths) share the same helper.
- The `_sio`, `_loop` sentinels default to `None` so an emit before the loop is captured drops silently — appropriate for a "progress event I don't have a channel for yet" case.

**Negative**
- Adds a shim (`events.emit`) that developers must remember to use instead of `sio.emit`. Enforced by code review + module import boundary.
- If `run_coroutine_threadsafe` raises, the exception is swallowed — a telemetry emit failure never crashes a worker.

**Neutral**
- Compatible with our existing worker-thread architecture; no change to `run_sync`, `run_scan`, `run_extraction`.

## Related

- `backend/events.py` — the shim
- `backend/main.py` — server init + `_capture_loop`
- [System-Design.md](../System-Design.md#event-delivery-socketio)
