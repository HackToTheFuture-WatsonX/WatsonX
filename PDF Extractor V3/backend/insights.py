"""
insights.py — Extraction analytics for PDF Extractor V3.
Ported from InsightsFrame and get_log_history (pdf_extractor_ui_v2.py lines 1177–1324, 2048–2082).

Logs and tracking are read from the SQLite database (see db.py) — the single
source of truth. No filesystem log scanning.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter
from tracking import load_tracking
import db

router = APIRouter(prefix="/api/insights", tags=["insights"])


def get_log_history(period: str = "day") -> str:
    today  = datetime.now().date()
    cutoff = {
        "day":   today,
        "week":  today - timedelta(days=today.weekday()),
        "month": today.replace(day=1),
        "year":  today.replace(month=1, day=1),
    }.get(period.lower(), today)

    entries = db.logs_since(cutoff)  # newest first
    if not entries:
        return f"No log entries found for the selected period ({period})."

    lines = [f"=== LOG HISTORY ({period.upper()}) — {len(entries)} entr(y/ies) ==="]
    for entry in entries:
        when = entry["occurred_at"]
        ref  = entry.get("ref_number") or "UNKNOWN_REF"
        lines.append(f"\n[{when.strftime('%Y-%m-%d %H:%M:%S')}]  {ref}")
        content_lines = (entry.get("content") or "").splitlines()
        lines.append("\n".join(f"  {ln}" for ln in content_lines[:10]))
        if len(content_lines) > 10:
            lines.append(f"  … ({len(content_lines) - 10} more lines)")
    lines.append("\n=== END LOG HISTORY ===")
    return "\n".join(lines)


def _build_chart_data(period: str) -> list[dict]:
    """Build bar chart data buckets from the tracking database."""
    tracking  = load_tracking()
    files     = tracking.get("files", {})
    today     = datetime.now().date()
    buckets: dict[str, dict] = defaultdict(lambda: {"completed": 0, "pending": 0})

    for info in files.values():
        status = info.get("status", "Pending")
        raw    = info.get("last_extracted") or ""
        try:
            dt = datetime.fromisoformat(raw).date() if raw else today
        except Exception:
            dt = today

        if period == "day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "week":
            key = f"Week {dt.isocalendar()[1]:02d}, {dt.year}"
        elif period == "month":
            key = dt.strftime("%b %Y")
        else:
            key = str(dt.year)

        if status == "Completed":
            buckets[key]["completed"] += 1
        else:
            buckets[key]["pending"] += 1

    return [
        {"period": k, "completed": v["completed"], "pending": v["pending"]}
        for k, v in sorted(buckets.items())
    ]


@router.get("")
def insights(period: str = "month"):
    """Return stat cards + chart data for the given period."""
    tracking  = load_tracking()
    files     = tracking.get("files", {})
    total     = len(files)
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    pending   = total - completed

    chart = _build_chart_data(period)
    return {
        "stats":  {"total": total, "completed": completed, "pending": pending},
        "chart":  chart,
        "period": period,
    }


@router.get("/logs")
def insights_logs(period: str = "week"):
    """Return plain-text log history."""
    return {"logs": get_log_history(period)}
