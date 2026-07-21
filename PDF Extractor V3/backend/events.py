"""
events.py — SocketIO event name constants + thread-safe emit helper.

Shared by backend workers (sync/scanner/extractor) and referenced in the
frontend. The AsyncServer created in main.py runs on the uvicorn asyncio event
loop; background worker threads must therefore schedule their emits back onto
that loop instead of calling sio.emit() directly (which is not safe from a
plain thread and silently drops messages).
"""
import asyncio
from typing import Optional

# ── Sync events ────────────────────────────────────────────────────────────────
SYNC_LOG  = "sync:log"
SYNC_DONE = "sync:done"

# ── Scan events ──────────────────────────────────────────────────────────────
SCAN_PROGRESS = "scan:progress"
SCAN_DONE     = "scan:done"

# ── Upload events ─────────────────────────────────────────────────────────────
# Per-file progress for the Scan page's Upload Files button. Each event's data:
#   {"name": "...", "state": "saving"|"uploaded"|"skipped"|"error",
#    "reason": "..." (state != "saving"),
#    "index": 1-based file index, "total": total files in this batch}
UPLOAD_PROGRESS = "upload:progress"
UPLOAD_DONE     = "upload:done"

# ── Extract events ─────────────────────────────────────────────────────────────
EXTRACT_PROGRESS = "extract:progress"
EXTRACT_RESULT   = "extract:result"
EXTRACT_DONE     = "extract:done"


# ── Thread-safe emit infrastructure ──────────────────────────────────────────
# main.py injects the AsyncServer instance and the running asyncio loop here.
_sio = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def configure(sio, loop: asyncio.AbstractEventLoop) -> None:
    """Called once by main.py after the server + event loop are created."""
    global _sio, _loop
    _sio = sio
    _loop = loop


def emit(event: str, data) -> None:
    """
    Emit a SocketIO event from ANY thread.

    With async_mode="asgi", sio.emit is a coroutine that must run on the
    uvicorn event loop. Worker threads call this helper, which schedules the
    coroutine thread-safely via run_coroutine_threadsafe. If the loop isn't
    ready yet (very early startup) the emit is silently dropped, which is fine
    for progress messages.
    """
    if _sio is None or _loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_sio.emit(event, data), _loop)
    except Exception:
        # Never let a telemetry emit crash a worker thread.
        pass
