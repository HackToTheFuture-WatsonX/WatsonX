"""
main.py — FastAPI + Flask-SocketIO server entry point for PDF Extractor V3.

Usage:
    python main.py                          # dev: auto-finds free port, data in backend/
    python main.py --port 8765              # dev: specific port
    python main.py --port 8765 --data-dir C:\\Users\\user\\AppData\\Roaming\\PDF Extractor V3
        # production: Electron passes --data-dir so config.json is read from userData
"""
import argparse
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr so unicode characters (e.g. arrows, em-dashes)
# never crash the process when Electron pipes output through a cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Ensure backend directory is on the path (important inside PyInstaller bundle)

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ── Parse args FIRST, before any module imports that call read_config() ──────
_parser = argparse.ArgumentParser(description="PDF Extractor V3 Backend")
_parser.add_argument("--port",     type=int,   default=None,
                     help="Port to listen on (auto-detected if omitted)")
_parser.add_argument("--data-dir", type=str,   default=None, dest="data_dir",
                     help="User data directory for config.json, tracking_db.json, logs")
_args = _parser.parse_args()

# Apply data-dir override before any config.py imports resolve paths
if _args.data_dir:
    from config import set_data_dir
    set_data_dir(_args.data_dir)

# Initialize the SQLite database (creates schema on first run) now that the
# data dir is resolved. Must happen before any router imports touch the DB.
import db
db.init_db()


import asyncio

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ports import find_free_port, write_port_file
import events
import scanner, sync, extractor, viewer, insights, chat, settings

APP_VERSION = "3.0.0"

# ── SocketIO server (ASGI mode) ───────────────────────────────────────────────
# async_mode="asgi" so the server rides the uvicorn asyncio event loop. The old
# "threading" mode was incompatible with the ASGIApp/uvicorn combo and silently
# dropped events emitted from background worker threads (Sync/Extract showed no
# live progress). Worker threads now emit via events.emit(), which schedules the
# coroutine back onto the captured loop with run_coroutine_threadsafe.
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode="asgi",
    logger=False,
    engineio_logger=False,
)


# ── FastAPI app ───────────────────────────────────────────────────────────────
_fastapi = FastAPI(
    title="PDF Extractor V3 API",
    version=APP_VERSION,
    description="Background Check Report Automation V3 — FastAPI backend",
)

_fastapi.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
_fastapi.include_router(scanner.router)
_fastapi.include_router(sync.router)
_fastapi.include_router(extractor.router)
_fastapi.include_router(viewer.router)
_fastapi.include_router(insights.router)
_fastapi.include_router(chat.router)
_fastapi.include_router(settings.router)


@_fastapi.on_event("startup")
async def _capture_loop():
    """Capture the running uvicorn asyncio loop so worker threads can emit
    SocketIO events thread-safely via events.emit()."""
    events.configure(sio, asyncio.get_running_loop())


@_fastapi.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}



# ── Wrap with SocketIO ASGI middleware ────────────────────────────────────────
app = socketio.ASGIApp(sio, other_asgi_app=_fastapi)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = _args.port if _args.port else find_free_port(8765)
    write_port_file(port)

    print(f"[V3 Backend] Starting on http://127.0.0.1:{port}")
    print(f"[V3 Backend] API docs -> http://127.0.0.1:{port}/docs")
    if _args.data_dir:
        print(f"[V3 Backend] Data dir -> {_args.data_dir}")


    # Pass the app object directly (NOT the "main:app" import string): inside a
    # PyInstaller frozen bundle there is no importable "main" module on sys.path,
    # so the string form fails with "Could not import module 'main'".
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="warning",
    )

