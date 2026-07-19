"""
start_v3.py — Development mode launcher for PDF Extractor V3.
Starts the FastAPI backend and Vite dev server, opens the browser.

Usage:
    python start_v3.py
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
BACKEND  = BASE_DIR / "backend"
FRONTEND = BASE_DIR / "frontend"

_SKIP_PORTS = {5000, 8080, 47321}


def find_free_port(preferred: int = 8765, max_attempts: int = 20) -> int:
    candidate = preferred
    attempts  = 0
    while attempts < max_attempts:
        if candidate in _SKIP_PORTS:
            candidate += 1; continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                s.bind(("127.0.0.1", candidate))
            return candidate
        except OSError:
            candidate += 1; attempts += 1
    raise RuntimeError(f"No free port found near {preferred}")


def wait_for_health(port: int, timeout: float = 30.0) -> bool:
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("=" * 60)
    print("  PDF Extractor V3 — Development Launcher")
    print("=" * 60)

    api_port = find_free_port(8765)
    print(f"  API port   : {api_port}")

    # Write port file + Vite .env.local
    (BACKEND / ".v3_port").write_text(str(api_port), encoding="utf-8")
    (FRONTEND / ".env.local").write_text(f"VITE_API_PORT={api_port}\n", encoding="utf-8")
    print(f"  Written    : backend/.v3_port, frontend/.env.local")

    # Start FastAPI backend
    python = sys.executable
    backend_proc = subprocess.Popen(
        [python, "main.py", "--port", str(api_port)],
        cwd=str(BACKEND),
    )
    print(f"  Backend PID: {backend_proc.pid}")

    # Wait for backend to be ready
    print("  Waiting for backend…", end="", flush=True)
    if not wait_for_health(api_port):
        print(" FAILED. Backend did not start in time.")
        backend_proc.terminate()
        sys.exit(1)
    print(" ready!")

    # Start Vite dev server
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    vite_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(FRONTEND),
    )
    print(f"  Vite PID   : {vite_proc.pid}")
    print("  Waiting for Vite…", end="", flush=True)
    time.sleep(3)
    print(" ready!")

    vite_url = "http://localhost:5173"
    print(f"\n  Opening    : {vite_url}")
    print(f"  API docs   : http://127.0.0.1:{api_port}/docs")
    print("\n  Press Ctrl+C to stop both servers.\n")
    webbrowser.open(vite_url)

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\n  Stopping servers…")
        backend_proc.terminate()
        vite_proc.terminate()
        print("  Done. Goodbye!")


if __name__ == "__main__":
    main()
