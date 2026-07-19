"""
tracking.py — Tracking database helpers for PDF Extractor V3.

Backed by SQLite (see db.py) — the database is the single source of truth.
The load_tracking()/save_tracking() signatures are preserved as thin wrappers
so existing call sites (scanner, extractor, insights, chat) work unchanged.
"""
import db


def load_tracking() -> dict:
    """Return the tracking DB in the legacy shape: {"files": {rel_key: {...}}}."""
    return db.tracking_get_all()


def save_tracking(tracking: dict) -> None:
    """Persist the full tracking dict ({"files": {...}}) to the database."""
    db.tracking_replace_all(tracking)
