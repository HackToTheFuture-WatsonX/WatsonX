"""
tracking.py — Tracking database helpers for PDF Extractor V3.
Ported from pdf_extractor_ui_v2.py (lines 230–239).
"""
import json
from config import _tracking_path


def load_tracking() -> dict:
    path = _tracking_path()
    if path.exists():
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {"files": {}}


def save_tracking(db: dict) -> None:
    path = _tracking_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
