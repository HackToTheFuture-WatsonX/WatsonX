"""
db.py — SQLite persistence layer for PDF Extractor V3.

Single source of truth for all application data:
  - config          : key/value store for the full config dict (JSON per top-level section)
  - tracking_files  : one row per tracked PDF (keyed by rel_key)
  - jwt_config      : Box JWT service-account JSON (single row)
  - extraction_logs : per-extraction log entries (replaces .log files)

The DB file lives in the data dir (backend/ in dev, %APPDATA%/PDF Extractor V3/
in production) — resolved via config._data_dir() so the --data-dir override applies.

Uses only the Python stdlib `sqlite3`. No ORM. Connections are opened per-call
(SQLite handles this cheaply) with WAL mode for concurrent read/write from the
background worker threads (scanner/extractor/sync).
"""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_FILENAME = "pdf_extractor_v3.db"

_init_lock = threading.Lock()
_initialized_for: Path | None = None


def _db_path() -> Path:
    # Imported lazily to respect set_data_dir() ordering in main.py
    from config import _data_dir
    return _data_dir() / DB_FILENAME


def _connect() -> sqlite3.Connection:
    """Open a connection with sane defaults, ensuring schema exists."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables once per data-dir. Cheap CREATE IF NOT EXISTS otherwise."""
    global _initialized_for
    path = _db_path()
    if _initialized_for == path:
        return
    with _init_lock:
        if _initialized_for == path:
            return
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS config (
                section TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tracking_files (
                rel_key        TEXT PRIMARY KEY,
                name           TEXT,
                status         TEXT DEFAULT 'Pending',
                last_extracted TEXT,
                ref_number     TEXT,
                local_path     TEXT,
                archive_path   TEXT
            );

            CREATE TABLE IF NOT EXISTS jwt_config (
                id    INTEGER PRIMARY KEY CHECK (id = 1),
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extraction_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ref_number TEXT,
                occurred_at TEXT NOT NULL,
                content    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_logs_occurred_at
                ON extraction_logs (occurred_at);
            """
        )
        conn.commit()
        _initialized_for = path


# ── Config (key/value by top-level section) ──────────────────────────────────

def config_get_all() -> dict:
    """Return the full config dict assembled from section rows. Empty dict if none."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT section, value FROM config").fetchall()
    finally:
        conn.close()
    result: dict = {}
    for row in rows:
        try:
            result[row["section"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            result[row["section"]] = row["value"]
    return result


def config_replace_all(cfg: dict) -> None:
    """Replace the entire config with the given dict (one row per top-level key)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM config")
        for section, value in cfg.items():
            payload = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) \
                else json.dumps(value, ensure_ascii=False)
            conn.execute(
                "INSERT INTO config (section, value) VALUES (?, ?)",
                (section, payload),
            )
        conn.commit()
    finally:
        conn.close()


def config_exists() -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM config").fetchone()
        return bool(row["n"])
    finally:
        conn.close()


# ── Tracking files ────────────────────────────────────────────────────────────

_TRACK_COLS = ("name", "status", "last_extracted", "ref_number",
               "local_path", "archive_path")


def tracking_get_all() -> dict:
    """Return tracking DB in the legacy shape: {"files": {rel_key: {...}}}."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT rel_key, name, status, last_extracted, ref_number, "
            "local_path, archive_path FROM tracking_files"
        ).fetchall()
    finally:
        conn.close()
    files: dict = {}
    for row in rows:
        entry = {
            "name":           row["name"],
            "status":         row["status"],
            "last_extracted": row["last_extracted"],
            "ref_number":     row["ref_number"],
            "local_path":     row["local_path"],
        }
        if row["archive_path"]:
            entry["archive_path"] = row["archive_path"]
        files[row["rel_key"]] = entry
    return {"files": files}


def tracking_replace_all(db: dict) -> None:
    """Replace all tracking rows from the legacy {"files": {...}} dict."""
    files = db.get("files", {}) if isinstance(db, dict) else {}
    conn = _connect()
    try:
        conn.execute("DELETE FROM tracking_files")
        for rel_key, info in files.items():
            info = info or {}
            conn.execute(
                "INSERT INTO tracking_files "
                "(rel_key, name, status, last_extracted, ref_number, local_path, archive_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rel_key,
                    info.get("name"),
                    info.get("status", "Pending"),
                    info.get("last_extracted"),
                    info.get("ref_number"),
                    info.get("local_path"),
                    info.get("archive_path"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ── JWT config ────────────────────────────────────────────────────────────────

def jwt_config_set(parsed: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO jwt_config (id, value) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET value = excluded.value",
            (json.dumps(parsed, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()


def jwt_config_get() -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM jwt_config WHERE id = 1").fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return None


def jwt_config_exists() -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM jwt_config WHERE id = 1").fetchone()
        return bool(row["n"])
    finally:
        conn.close()


# ── Extraction logs ─────────────────────────────────────────────────────────

def log_add(ref_number: str, when: datetime, content: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO extraction_logs (ref_number, occurred_at, content) "
            "VALUES (?, ?, ?)",
            (ref_number, when.isoformat(timespec="seconds"), content),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def logs_since(cutoff_date) -> list[dict]:
    """Return logs whose occurred_at date is >= cutoff_date (a datetime.date).
    Newest first. Each item: {ref_number, occurred_at (datetime), content}."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT ref_number, occurred_at, content FROM extraction_logs "
            "ORDER BY occurred_at DESC"
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for row in rows:
        raw = row["occurred_at"]
        try:
            dt = datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            dt = datetime.now()
        if dt.date() >= cutoff_date:
            out.append({
                "ref_number": row["ref_number"],
                "occurred_at": dt,
                "content": row["content"],
            })
    return out


def init_db() -> None:
    """Explicitly initialize the schema (called from main.py after set_data_dir)."""
    conn = _connect()
    conn.close()
