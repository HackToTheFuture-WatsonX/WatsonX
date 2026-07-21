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

            -- ── Audit ────────────────────────────────────────────────────────
            -- Persisted, flattened audit row written at extraction time. This
            -- is the real-time source of truth for the Audit page + Insights,
            -- so stats never need to re-parse JSON files on disk.
            CREATE TABLE IF NOT EXISTS audit_records (
                ref_number             TEXT PRIMARY KEY,
                candidate_name         TEXT DEFAULT '',
                initiation_date        TEXT DEFAULT '',
                final_report_date      TEXT DEFAULT '',
                supplementary_report_date TEXT DEFAULT '',
                overall_bgv_result     TEXT DEFAULT '',
                e1                     TEXT DEFAULT '',
                e2                     TEXT DEFAULT '',
                e3                     TEXT DEFAULT '',
                e4                     TEXT DEFAULT '',
                e5                     TEXT DEFAULT '',
                ref1                   TEXT DEFAULT '',
                ref2                   TEXT DEFAULT '',
                adverse_media          TEXT DEFAULT '',
                global_sanctions       TEXT DEFAULT '',
                bankruptcy             TEXT DEFAULT '',
                financial_credit       TEXT DEFAULT '',
                directorship           TEXT DEFAULT '',
                civil_litigation       TEXT DEFAULT '',
                professional_license   TEXT DEFAULT '',
                social_media           TEXT DEFAULT '',
                source_json            TEXT DEFAULT '',
                updated_at             TEXT
            );

            -- User-editable override fields keyed by ref_number. A row here only
            -- exists once a user has set at least one override. isCompliant here
            -- is a manual override that wins over the derived default.
            CREATE TABLE IF NOT EXISTS audit_overrides (
                ref_number           TEXT PRIMARY KEY,
                candidate_name       TEXT,
                onboarding_date      TEXT,
                background_check_date TEXT,
                is_compliant         TEXT,
                updated_at           TEXT
            );

            -- Read-only view that LEFT JOINs records + overrides and derives the
            -- final displayed columns (incl. isCompliant). Serves the Audit page,
            -- the Excel export, and the audit-driven Insights stats.
            CREATE VIEW IF NOT EXISTS audit_resource AS
            SELECT
                r.ref_number                                        AS "S/N",
                COALESCE(o.candidate_name, r.candidate_name)        AS "Candidate Name",
                r.initiation_date                                   AS "Initiation Date",
                r.final_report_date                                 AS "Final Report Sent Date",
                r.supplementary_report_date                         AS "Supplementary Report Sent Date",
                r.overall_bgv_result                                AS "Overall BGV Result",
                r.e1                                                AS "E1 (most recent)",
                r.e2                                                AS "E2",
                r.e3                                                AS "E3",
                r.e4                                                AS "E4",
                r.e5                                                AS "E5",
                r.ref1                                              AS "REF 1",
                r.ref2                                              AS "REF 2",
                r.adverse_media                                     AS "Adverse Media Check",
                r.global_sanctions                                  AS "Global Sanctions",
                r.bankruptcy                                        AS "Bankruptcy Check",
                r.financial_credit                                  AS "Financial/Credit Check",
                r.directorship                                      AS "Directorship Check (DTI Only)",
                r.civil_litigation                                  AS "Civil Litigation Check",
                r.professional_license                              AS "Professional License Qualification",
                r.social_media                                      AS "Social Media Screening",
                COALESCE(o.candidate_name, r.candidate_name)        AS "Name",
                COALESCE(o.onboarding_date, '')                     AS "Onboarding Date",
                COALESCE(o.background_check_date, r.final_report_date) AS "Background Check Date",
                CASE
                    WHEN o.is_compliant IS NOT NULL AND o.is_compliant != ''
                        THEN o.is_compliant
                    WHEN r.overall_bgv_result LIKE 'Cleared%'
                         AND COALESCE(o.background_check_date, r.final_report_date) != ''
                        THEN 'true'
                    ELSE 'false'
                END                                                 AS "isCompliant"
            FROM audit_records r
            LEFT JOIN audit_overrides o ON o.ref_number = r.ref_number;
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


# ── Audit records / overrides / resource view ────────────────────────────────

# Column order matches the audit_records table (excluding ref_number PK and
# updated_at, which are handled explicitly).
_AUDIT_RECORD_COLS = (
    "candidate_name", "initiation_date", "final_report_date",
    "supplementary_report_date", "overall_bgv_result",
    "e1", "e2", "e3", "e4", "e5", "ref1", "ref2",
    "adverse_media", "global_sanctions", "bankruptcy", "financial_credit",
    "directorship", "civil_litigation", "professional_license", "social_media",
    "source_json",
)


def audit_record_upsert(ref_number: str, fields: dict) -> None:
    """Insert or replace the persisted flattened audit row for a reference.

    `fields` may contain any subset of _AUDIT_RECORD_COLS; missing keys default
    to ''. Called at extraction time (and by the backfill) so the audit_resource
    view is always a real-time source of truth.
    """
    ref = (ref_number or "").strip()
    if not ref:
        return
    values = [ref] + [str(fields.get(c, "") or "") for c in _AUDIT_RECORD_COLS]
    values.append(datetime.now().isoformat(timespec="seconds"))
    placeholders = ", ".join(["?"] * (len(_AUDIT_RECORD_COLS) + 2))
    col_list = ", ".join(("ref_number",) + _AUDIT_RECORD_COLS + ("updated_at",))
    conn = _connect()
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO audit_records ({col_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        conn.close()


_AUDIT_OVERRIDE_COLS = (
    "candidate_name", "onboarding_date", "background_check_date", "is_compliant",
)


def audit_override_upsert(ref_number: str, fields: dict) -> None:
    """Merge user-editable override fields for a reference.

    Only the keys present in `fields` are updated; others are preserved. Pass an
    empty string to clear a field, or None to leave it untouched.
    """
    ref = (ref_number or "").strip()
    if not ref:
        return
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT candidate_name, onboarding_date, background_check_date, is_compliant "
            "FROM audit_overrides WHERE ref_number = ?",
            (ref,),
        ).fetchone()
        current = dict(row) if row else {c: None for c in _AUDIT_OVERRIDE_COLS}
        for c in _AUDIT_OVERRIDE_COLS:
            if c in fields and fields[c] is not None:
                current[c] = fields[c]
        conn.execute(
            "INSERT OR REPLACE INTO audit_overrides "
            "(ref_number, candidate_name, onboarding_date, background_check_date, "
            " is_compliant, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ref,
                current.get("candidate_name"),
                current.get("onboarding_date"),
                current.get("background_check_date"),
                current.get("is_compliant"),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def audit_override_get(ref_number: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT ref_number, candidate_name, onboarding_date, "
            "background_check_date, is_compliant, updated_at "
            "FROM audit_overrides WHERE ref_number = ?",
            ((ref_number or "").strip(),),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def audit_resource_all() -> list[dict]:
    """Return every row of the audit_resource view (labelled column names)."""
    conn = _connect()
    try:
        rows = conn.execute('SELECT * FROM audit_resource ORDER BY "S/N"').fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def audit_record_count() -> int:
    conn = _connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM audit_records").fetchone()
        return int(row["n"])
    finally:
        conn.close()


def audit_records_clear() -> None:
    """Remove all persisted audit rows (overrides are preserved)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM audit_records")
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Explicitly initialize the schema (called from main.py after set_data_dir)."""
    conn = _connect()
    conn.close()

