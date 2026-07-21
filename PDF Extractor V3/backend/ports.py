"""
ports.py — Dynamic port finder for PDF Extractor V3.
Probes ports starting at `preferred` until a free one is found.
Writes/reads the chosen port to/from .v3_port in BASE_DIR.
"""
import socket
from pathlib import Path

BASE_DIR  = Path(__file__).parent.resolve()
PORT_FILE = BASE_DIR / ".v3_port"

# Ports already used elsewhere in the workspace — skip these
_SKIP_PORTS = {5000, 8080, 47321}


def find_free_port(preferred: int = 8765, max_attempts: int = 20) -> int:
    """
    Starting at `preferred`, probe each port with socket.bind().
    Returns the first available port that is not in _SKIP_PORTS.
    Raises RuntimeError if none found within max_attempts.
    """
    candidate = preferred
    attempts  = 0
    while attempts < max_attempts:
        if candidate in _SKIP_PORTS:
            candidate += 1
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                s.bind(("127.0.0.1", candidate))
            return candidate
        except OSError:
            candidate += 1
            attempts  += 1
    raise RuntimeError(
        f"No free port found in range [{preferred}, {preferred + max_attempts}) "
        f"(skipped: {_SKIP_PORTS})"
    )


def write_port_file(port: int) -> None:
    PORT_FILE.write_text(str(port), encoding="utf-8")


def read_port_file() -> int:
    return int(PORT_FILE.read_text(encoding="utf-8").strip())
