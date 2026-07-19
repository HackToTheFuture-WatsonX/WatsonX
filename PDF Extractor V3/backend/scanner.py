"""
scanner.py — Local Folder PDF scanner for PDF Extractor V3.
Ported from ScanFolderFrame._scan_worker (pdf_extractor_ui_v2.py lines 1108–1171).
Exposes FastAPI router + SocketIO-emitting worker.
"""
import threading
from pathlib import Path
from fastapi import APIRouter
from config import local_folder, extracted_folder, archive_folder
from tracking import load_tracking, save_tracking
import events

router = APIRouter(prefix="/api/scan", tags=["scan"])

# SocketIO instance — injected by main.py after creation
_sio = None

def set_sio(sio):
    global _sio
    _sio = sio


def _emit(event: str, data):
    if _sio:
        _sio.emit(event, data)


def run_scan() -> dict:
    """
    Walk the Local Folder, register all .pdf as Pending (skip Extracted/ Archive/).
    Purge stale entries. Returns summary dict.
    """
    local   = local_folder()
    ext_dir = extracted_folder()
    arch    = archive_folder()
    db      = load_tracking()
    found   = 0

    for pdf_path in local.rglob("*.pdf"):
        try:
            pdf_path.relative_to(ext_dir)
            continue
        except ValueError:
            pass
        try:
            pdf_path.relative_to(arch)
            continue
        except ValueError:
            pass

        rel_key  = str(pdf_path.relative_to(local))
        existing = db.get("files", {}).get(rel_key, {})
        db["files"][rel_key] = {
            "name":           pdf_path.name,
            "status":         "Pending",
            "last_extracted": existing.get("last_extracted"),
            "ref_number":     existing.get("ref_number"),
            "local_path":     str(pdf_path),
        }
        found += 1
        _emit(events.SCAN_PROGRESS, {"found": found, "name": pdf_path.name})

    # Purge stale entries
    stale = []
    for rel_key, info in db.get("files", {}).items():
        src  = Path(info.get("local_path", local / rel_key))
        arch_path = Path(info.get("archive_path", ""))
        if not src.exists() and not arch_path.exists():
            stale.append(rel_key)
    for rel_key in stale:
        del db["files"][rel_key]

    save_tracking(db)

    files     = db.get("files", {})
    pending   = sum(1 for f in files.values() if f.get("status") == "Pending")
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    summary   = {"found": found, "total": len(files), "pending": pending, "completed": completed}
    _emit(events.SCAN_DONE, summary)
    return summary


def _scan_thread():
    try:
        run_scan()
    except Exception as exc:
        _emit(events.SCAN_DONE, {"error": str(exc)})


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/run")
def scan_run():
    """Trigger a scan in the background. Progress emitted via SocketIO."""
    threading.Thread(target=_scan_thread, daemon=True).start()
    return {"status": "started"}


@router.get("/files")
def scan_files():
    """Return current tracking DB contents."""
    db    = load_tracking()
    files = db.get("files", {})
    items = []
    for rel_key, info in files.items():
        items.append({
            "key":            rel_key,
            "name":           info.get("name", rel_key),
            "status":         info.get("status", "Pending"),
            "last_extracted": info.get("last_extracted"),
            "ref_number":     info.get("ref_number"),
            "local_path":     info.get("local_path", ""),
        })
    pending   = sum(1 for i in items if i["status"] == "Pending")
    completed = sum(1 for i in items if i["status"] == "Completed")
    return {"files": items, "total": len(items), "pending": pending, "completed": completed}
