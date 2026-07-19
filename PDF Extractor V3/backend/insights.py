"""
insights.py — Extraction analytics for PDF Extractor V3.
Ported from InsightsFrame and get_log_history (pdf_extractor_ui_v2.py lines 1177–1324, 2048–2082).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter
from config import _log_history_dir
from tracking import load_tracking

router = APIRouter(prefix="/api/insights", tags=["insights"])


def get_log_history(period: str = "day") -> str:
    today  = datetime.now().date()
    cutoff = {
        "day":   today,
        "week":  today - timedelta(days=today.weekday()),
        "month": today.replace(day=1),
        "year":  today.replace(month=1, day=1),
    }.get(period.lower(), today)

    if not LOG_HISTORY_DIR.exists():
        return "No log history found."

    log_files = []
    for log_path in LOG_HISTORY_DIR.rglob("*.log"):
        parts    = log_path.parts
        date_str = parts[-2] if len(parts) >= 2 else ""
        try:
            log_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            log_date = today
        if log_date >= cutoff:
            log_files.append((log_date, log_path))

    if not log_files:
        return f"No log entries found for the selected period ({period})."

    log_files.sort(key=lambda x: x[0], reverse=True)
    lines = [f"=== LOG HISTORY ({period.upper()}) — {len(log_files)} file(s) ==="]
    for log_date, log_path in log_files:
        lines.append(f"\n[{log_date}]  {log_path.name}")
        try:
            content_lines = log_path.read_text(encoding="utf-8").splitlines()
            lines.append("\n".join(f"  {ln}" for ln in content_lines[:10]))
            if len(content_lines) > 10:
                lines.append(f"  … ({len(content_lines) - 10} more lines)")
        except Exception:
            lines.append("  (could not read log file)")
    lines.append("\n=== END LOG HISTORY ===")
    return "\n".join(lines)


def _build_chart_data(period: str) -> list[dict]:
    """Build bar chart data buckets from tracking_db.json."""
    db        = load_tracking()
    files     = db.get("files", {})
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
    db        = load_tracking()
    files     = db.get("files", {})
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
