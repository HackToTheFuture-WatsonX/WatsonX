"""
WatsonX Challenge — Web Server Launcher
========================================
Double-click this (or the compiled Start WatsonX Server.exe) to start the
Flask server and open the web app in your default browser automatically.

The console window stays open so you can see logs and press Ctrl+C to stop.

Cache behaviour
---------------
* On STARTUP  — __pycache__ folders and all .pyc/.pyo files under the app
  directory are wiped so Python always compiles fresh bytecode from the
  latest source.  This also clears any stale Jinja2 / Werkzeug caches that
  live alongside the source tree.
* On SHUTDOWN — the same sweep runs again via atexit so the folder is left
  clean for the next launch.

Single-instance lock
--------------------
A socket bound to LOCK_PORT acts as a mutex.  A second double-click just
opens the browser tab instead of spawning a duplicate server.
"""

import atexit
import os
import shutil
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path

# ── Resolve the web-app folder whether frozen or run from source ──────────────
if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle — exe lives inside the web-app folder
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

APP_URL   = "http://127.0.0.1:5000"
LOCK_PORT = 47321   # arbitrary; used only as a single-instance lock


# ─────────────────────────────────────────────────────────────────────────────
# Cache utilities
# ─────────────────────────────────────────────────────────────────────────────

def clear_cache() -> None:
    """
    Remove all Python bytecode caches under APP_DIR:
      • every __pycache__ directory (and its contents)
      • any stray .pyc / .pyo files sitting outside __pycache__ dirs

    Safe to call at startup and shutdown — the files are always re-generated
    by Python on the next import, so nothing is permanently lost.
    """
    removed_dirs  = 0
    removed_files = 0

    for root, dirs, files in os.walk(APP_DIR, topdown=True):
        # Remove __pycache__ directories in-place so os.walk won't descend
        for d in list(dirs):
            if d == "__pycache__":
                target = Path(root) / d
                try:
                    shutil.rmtree(target)
                    removed_dirs += 1
                except Exception as e:
                    print(f"  [cache] Could not remove {target}: {e}")
                dirs.remove(d)   # prevent os.walk from descending into it

        # Remove stray .pyc / .pyo files
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                target = Path(root) / f
                try:
                    target.unlink()
                    removed_files += 1
                except Exception as e:
                    print(f"  [cache] Could not remove {target}: {e}")

    if removed_dirs or removed_files:
        parts = []
        if removed_dirs:
            parts.append(f"{removed_dirs} __pycache__ folder{'s' if removed_dirs > 1 else ''}")
        if removed_files:
            parts.append(f"{removed_files} .pyc file{'s' if removed_files > 1 else ''}")
        print(f"  [cache] Cleared: {', '.join(parts)}")
    else:
        print("  [cache] Nothing to clear — already clean.")


# ─────────────────────────────────────────────────────────────────────────────
# Single-instance guard
# ─────────────────────────────────────────────────────────────────────────────

def already_running() -> bool:
    """
    Try to bind a throw-away TCP socket on LOCK_PORT.
    If it fails, another instance of this launcher is already holding the port.
    """
    try:
        _lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        _lock_sock.bind(("127.0.0.1", LOCK_PORT))
        _lock_sock.listen(1)
        # Keep the socket alive for the life of the process.
        already_running._sock = _lock_sock
        return False
    except OSError:
        return True


def open_browser_delayed(url: str, delay: float = 2.0) -> None:
    """Open the browser after a short delay (runs in a daemon thread)."""
    time.sleep(delay)
    webbrowser.open(url)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    os.chdir(APP_DIR)

    # ── Single-instance guard ─────────────────────────────────────────────────
    if already_running():
        print("=" * 60)
        print("  WatsonX Challenge — server is already running.")
        print(f"  Opening {APP_URL} in your browser …")
        print("=" * 60)
        webbrowser.open(APP_URL)
        input("\n  Press Enter to close this window.")
        return

    print("=" * 60)
    print("  WatsonX Challenge — Web App Server")
    print("=" * 60)
    print(f"  Folder : {APP_DIR}")
    print(f"  URL    : {APP_URL}")
    print()

    # ── Startup cache clear ───────────────────────────────────────────────────
    print("  Clearing cache before starting …")
    clear_cache()
    print()

    # ── Register shutdown cache clear via atexit ──────────────────────────────
    def _on_shutdown() -> None:
        print("\n  Clearing cache on shutdown …")
        clear_cache()
        print("  Server stopped. Goodbye!")

    atexit.register(_on_shutdown)

    # ── Import the Flask app from the web-app folder ──────────────────────────
    print("  Starting Flask server …")
    print("  Press Ctrl+C to stop the server.")
    print()

    sys.path.insert(0, str(APP_DIR))
    from app import app  # noqa: PLC0415  (import inside function is intentional)

    # Always reload templates from disk — no stale Jinja cache
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Open the browser in a background thread so Flask can start first
    t = threading.Thread(target=open_browser_delayed, args=(APP_URL,), daemon=True)
    t.start()

    # Run Flask in the foreground (blocks until Ctrl+C or process exit)
    try:
        app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)
    except KeyboardInterrupt:
        pass   # atexit handler prints the goodbye message


if __name__ == "__main__":
    main()
