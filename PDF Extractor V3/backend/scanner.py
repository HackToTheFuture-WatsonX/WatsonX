"""
scanner.py — Local Folder PDF scanner for PDF Extractor V3.
Ported from ScanFolderFrame._scan_worker (pdf_extractor_ui_v2.py lines 1108–1171).
Exposes FastAPI router + SocketIO-emitting worker (thread-safe via events.emit()).
"""
import logging
import threading
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, File, UploadFile
from config import local_folder, extracted_folder, archive_folder
from tracking import load_tracking, save_tracking
import activity
import events

log = logging.getLogger("scanner")
if not log.handlers:
    log.setLevel(logging.INFO)
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[scanner] %(levelname)s %(message)s"))
    log.addHandler(_h)

router = APIRouter(prefix="/api/scan", tags=["scan"])

# Shared run-state so the frontend can rehydrate after navigating away.
_status = {"running": False, "last": None}
_cancel = threading.Event()


def _emit(event: str, data):
    events.emit(event, data)


def run_scan() -> dict:
    """
    Walk the Local Folder, register all .pdf as Pending (skip Extracted/ Archive/).
    Purge stale entries. Returns summary dict. Honors the _cancel event.
    """
    local   = local_folder()
    ext_dir = extracted_folder()
    arch    = archive_folder()
    db      = load_tracking()
    found   = 0

    for pdf_path in local.rglob("*.pdf"):
        if _cancel.is_set():
            break
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
    if _cancel.is_set():
        summary["cancelled"] = True
    _emit(events.SCAN_DONE, summary)
    return summary


def _scan_thread():
    _status["running"] = True
    _cancel.clear()
    try:
        summary = run_scan()
        _status["last"] = summary
        if summary.get("cancelled"):
            activity.write("SCAN", "Scan cancelled by user.", level="warning")
        else:
            activity.write(
                "SCAN",
                f"Scan complete — found {summary.get('found', 0)}, "
                f"total {summary.get('total', 0)}, "
                f"pending {summary.get('pending', 0)}, "
                f"completed {summary.get('completed', 0)}.",
                level="info",
            )
    except Exception as exc:
        _emit(events.SCAN_DONE, {"error": str(exc)})
        activity.write("SCAN", f"Scan failed: {exc}", level="error")
    finally:
        _status["running"] = False
        _cancel.clear()


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/run")
def scan_run():
    """Trigger a scan in the background. Progress emitted via SocketIO."""
    if _status["running"]:
        return {"status": "already_running"}
    threading.Thread(target=_scan_thread, daemon=True).start()
    return {"status": "started"}


@router.post("/cancel")
def scan_cancel():
    """Request cancellation of an in-progress scan."""
    if not _status["running"]:
        return {"status": "not_running"}
    _cancel.set()
    return {"status": "cancelling"}


@router.get("/status")
def scan_status():
    return {"running": _status["running"], "last": _status["last"]}


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


@router.post("/upload")
async def scan_upload(files: List[UploadFile] = File(...)):
    """Save uploaded PDFs into the Local Folder and register them for extraction.

    Skips (does not overwrite) any file whose name already exists in the Local
    Folder — this preserves the existing tracking entry so a previously-completed
    file is not reverted to Pending. Non-PDF uploads are rejected.

    Emits UPLOAD_PROGRESS Socket.IO events per file so the Scan page can show
    live progress. On completion, writes a single activity-log row (when
    settings.log_activity is enabled) so uploads are auditable alongside
    extractions on the Logs page.
    """
    local = local_folder()
    tracking = load_tracking()
    tracking.setdefault("files", {})

    uploaded: list[dict] = []
    skipped:  list[dict] = []
    errors:   list[dict] = []
    changed = False
    total = len(files)

    # Log the request as soon as it arrives so the operator can confirm from the
    # backend console that the button is actually reaching the server. Previous
    # symptom ("nothing happens on upload") was almost always the backend
    # running an old build without this endpoint — this line makes that visible.
    log.info("POST /api/scan/upload — %d file(s) → %s", total, local)
    for up in files:
        log.info("  incoming: name=%r content_type=%s", up.filename, up.content_type)

    def _emit(name: str, state: str, index: int, reason: str = "") -> None:
        events.emit(events.UPLOAD_PROGRESS, {
            "name":   name,
            "state":  state,
            "reason": reason,
            "index":  index,
            "total":  total,
        })

    for idx, up in enumerate(files, start=1):
        # Strip any path components a client might sneak in ("../evil.pdf" →
        # "evil.pdf"). UploadFile.filename comes straight from the multipart
        # part header — never trust it.
        raw_name  = up.filename or ""
        safe_name = Path(raw_name).name

        if not safe_name:
            errors.append({"name": raw_name, "error": "empty filename"})
            _emit(raw_name or "(no name)", "error", idx, "empty filename")
            await up.close()
            continue
        if not safe_name.lower().endswith(".pdf"):
            errors.append({"name": safe_name, "error": "not a PDF"})
            _emit(safe_name, "error", idx, "not a PDF")
            await up.close()
            continue

        target = local / safe_name
        if target.exists():
            skipped.append({"name": safe_name, "reason": "already exists",
                            "key": safe_name})
            _emit(safe_name, "skipped", idx, "already exists")
            await up.close()
            continue

        _emit(safe_name, "saving", idx)
        try:
            async with aiofiles.open(target, "wb") as out:
                # Stream in chunks so large PDFs don't have to fit in memory.
                while True:
                    chunk = await up.read(1024 * 1024)
                    if not chunk:
                        break
                    await out.write(chunk)
        except Exception as exc:  # noqa: BLE001
            # Partial write may have created the file — clean up so a retry
            # can succeed rather than tripping the "already exists" branch.
            try:
                if target.exists():
                    target.unlink()
            except Exception:
                pass
            errors.append({"name": safe_name, "error": str(exc)[:200]})
            _emit(safe_name, "error", idx, str(exc)[:200])
            await up.close()
            continue
        finally:
            await up.close()

        # Register the file in the tracking DB using the same shape run_scan()
        # writes (scanner.py:49-57) so it appears in the Scan table identically
        # to files discovered by a folder walk.
        rel_key = str(target.relative_to(local))
        tracking["files"][rel_key] = {
            "name":           safe_name,
            "status":         "Pending",
            "last_extracted": None,
            "ref_number":     None,
            "local_path":     str(target),
        }
        uploaded.append({"name": safe_name, "key": rel_key})
        _emit(safe_name, "uploaded", idx)
        changed = True

    if changed:
        save_tracking(tracking)

    files_map = tracking.get("files", {})
    totals = {
        "total":     len(files_map),
        "pending":   sum(1 for f in files_map.values() if f.get("status") == "Pending"),
        "completed": sum(1 for f in files_map.values() if f.get("status") == "Completed"),
    }

    # Write a single activity-log row summarising this upload batch so the
    # Logs page shows it alongside extractions and other transactions.
    log_lines = [
        f"Upload batch — {len(uploaded)} uploaded, "
        f"{len(skipped)} skipped, {len(errors)} failed.",
        "",
    ]
    for u in uploaded:
        log_lines.append(f"  [OK]   {u['name']}")
    for s in skipped:
        log_lines.append(f"  [SKIP] {s['name']} — {s['reason']}")
    for e in errors:
        log_lines.append(f"  [ERR]  {e['name']} — {e['error']}")
    # Batch level: any per-file failure → Warning; nothing wrote AND nothing
    # skipped → Warning (user picked files but none landed); otherwise Info.
    if errors:
        upload_level = "warning"
    elif not uploaded and skipped:
        upload_level = "info"  # duplicates are expected, not concerning
    elif not uploaded and not skipped:
        upload_level = "warning"  # picker returned files but none matched
    else:
        upload_level = "info"
    activity.write("UPLOAD", "\n".join(log_lines), level=upload_level)

    result = {
        "uploaded": uploaded,
        "skipped":  skipped,
        "errors":   errors,
        "totals":   totals,
    }
    events.emit(events.UPLOAD_DONE, result)
    log.info("upload done — %d uploaded, %d skipped, %d error(s)",
             len(uploaded), len(skipped), len(errors))
    return result
