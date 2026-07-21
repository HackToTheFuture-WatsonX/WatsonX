"""
activity.py — shared activity-log helper for PDF Extractor V3.

Every non-navigation transaction the backend performs (sync, scan, upload,
extract, ICA/Box test, ICA init, settings save, JWT upload, …) writes a single
row here so users can audit "what did the app do and when" from the Logs page.

The Logs page reads from db.extraction_logs (the ref/occurred_at/content triple
established by extractor.py). We reuse that table rather than creating a
second one — the Logs page filters/renders by ref, so a mixed-ref stream just
shows up as different rows.

Design rules:
- Respect settings.log_activity — if the user has disabled activity logging,
  everything here becomes a no-op.
- Never raise. A logging failure must never break the caller's transaction.
- Truncate absurdly long content so a runaway caller can't blow up the row.
"""
from __future__ import annotations

import logging
from datetime import datetime

import db
from config import read_config_safe

log = logging.getLogger("activity")

# Cap on a single log row's content so a pathological caller (or attacker who
# controls a filename we log) can't stuff megabytes into the DB.
_MAX_CONTENT_CHARS = 8000

# Machine-readable level tag written as the first line of every activity row.
# The Logs page reads this to classify Info/Warning/Error accurately, instead
# of guessing from keyword patterns in the content (which caused sync-completion
# messages containing "0 error(s)" to be misclassified as Error).
_LEVEL_PREFIX = "[[level="

_VALID_LEVELS = ("info", "warning", "error")


def _log_activity_enabled() -> bool:
    try:
        cfg = read_config_safe()
        return bool(cfg.get("settings", {}).get("log_activity", True))
    except Exception:
        # If we can't read the config, prefer logging to silence — the log is
        # exactly what the user needs to diagnose whatever went wrong.
        return True


def write(ref: str, content: str, *, when: datetime | None = None,
          level: str = "info") -> None:
    """Persist a single activity-log row. Safe to call from anywhere.

    Args:
        ref: short identifier grouping related rows (e.g. "SYNC", "SCAN",
             "UPLOAD", "SETTINGS", "ICA-INIT", "ICA-TEST", "BOX-TEST",
             "JWT-UPLOAD"). Shown as the ref column on the Logs page.
        content: multi-line human-readable body. First line becomes the row's
                 preview; keep it short and specific.
        when: override the timestamp (rarely useful outside tests).
        level: 'info' | 'warning' | 'error'. Prepended as a machine-readable
               tag so the Logs page can classify without keyword-matching.
    """
    if not _log_activity_enabled():
        return
    safe_ref = (ref or "").strip() or "ACTIVITY"
    lvl = (level or "info").strip().lower()
    if lvl not in _VALID_LEVELS:
        lvl = "info"
    body = content or ""
    if len(body) > _MAX_CONTENT_CHARS:
        body = body[:_MAX_CONTENT_CHARS] + "\n… (truncated)"
    tagged = f"{_LEVEL_PREFIX}{lvl}]] {body}"
    try:
        db.log_add(safe_ref, when or datetime.now(), tagged)
    except Exception as exc:  # noqa: BLE001
        log.warning("activity.write failed (ref=%s): %s", safe_ref, exc)
