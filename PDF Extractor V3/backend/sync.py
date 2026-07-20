"""
sync.py — Box-to-local sync for PDF Extractor V3.
Ported from sync_box_to_local (pdf_extractor_ui_v2.py lines 320–401).
Emits SocketIO events for live log streaming via events.emit() (thread-safe).
"""
import threading
from fastapi import APIRouter
from config import local_folder
from box_client import get_box_client
import events

router = APIRouter(prefix="/api/sync", tags=["sync"])

# Shared run-state so the frontend can rehydrate after navigating away.
_status = {"running": False, "last": None}
_cancel = threading.Event()


def _emit_log(msg: str):
    events.emit(events.SYNC_LOG, {"message": msg})


class _Cancelled(Exception):
    """Raised internally to unwind the sync loop when the user cancels."""


def sync_box_to_local() -> tuple[int, int, list[str]]:
    """
    Download all PDFs from Box folder_id → Local Folder.
    After each download moves source to archive_folder_id on Box.
    Returns (downloaded, skipped, errors).
    Honors the _cancel event between items.
    """
    downloaded = 0
    skipped    = 0
    errors: list[str] = []

    try:
        client, cfg = get_box_client()
    except Exception as exc:
        errors.append(str(exc))
        return 0, 0, errors

    box_cfg           = cfg["box"]
    folder_id         = box_cfg.get("folder_id", "0")
    archive_folder_id = box_cfg.get("archive_folder_id", "")
    local             = local_folder()

    _emit_log(f"Connecting to Box (source folder {folder_id})…")

    def _sync_folder(fid: str, dest, recurse: bool):
        nonlocal downloaded, skipped
        if _cancel.is_set():
            raise _Cancelled()
        try:
            items = list(client.folder(fid).get_items(limit=1000))
        except Exception as exc:
            errors.append(f"Cannot list folder {fid}: {exc}")
            return
        for item in items:
            if _cancel.is_set():
                raise _Cancelled()
            if item.type == "file" and item.name.lower().endswith(".pdf"):
                local_path = dest / item.name
                if local_path.exists():
                    skipped += 1
                    _emit_log(f"  Skip (exists): {item.name}")
                else:
                    try:
                        _emit_log(f"  Downloading: {item.name}")
                        data = client.file(item.id).content()
                        with open(local_path, "wb") as fh:
                            fh.write(data)
                        downloaded += 1
                        _emit_log(f"  ✅ Saved: {item.name}")
                        if archive_folder_id:
                            try:
                                client.file(item.id).move(
                                    parent_folder=client.folder(archive_folder_id)
                                )
                                _emit_log(f"  📦 Archived on Box: {item.name}")
                            except Exception as arc_exc:
                                _emit_log(f"  ⚠ Archive move failed ({item.name}): {arc_exc}")
                    except Exception as exc:
                        errors.append(f"Download failed ({item.name}): {exc}")
            elif item.type == "folder" and recurse:
                sub_dest = dest / item.name
                sub_dest.mkdir(parents=True, exist_ok=True)
                _emit_log(f"  Entering subfolder: {item.name}")
                _sync_folder(item.id, sub_dest, recurse)

    search_sub = cfg.get("settings", {}).get("search_subfolders", True)
    _sync_folder(folder_id, local, search_sub)
    # Surface each collected error in the live log so the user can see the
    # actual reason(s), not just a count.
    for err in errors:
        _emit_log(f"  ⚠ {err}")
    msg = f"Sync complete — {downloaded} downloaded, {skipped} skipped, {len(errors)} error(s)."
    _emit_log(msg)
    return downloaded, skipped, errors



def _sync_thread():
    _status["running"] = True
    _cancel.clear()
    try:
        downloaded, skipped, errors = sync_box_to_local()
        if _cancel.is_set():
            _emit_log("Sync cancelled by user.")
            events.emit(events.SYNC_DONE, {"cancelled": True})
            return
        from scanner import run_scan
        run_scan()
        _status["last"] = {
            "downloaded": downloaded, "skipped": skipped, "errors": errors,
        }
        events.emit(events.SYNC_DONE, {
            "downloaded": downloaded, "skipped": skipped, "errors": errors
        })
    except _Cancelled:
        _emit_log("Sync cancelled by user.")
        events.emit(events.SYNC_DONE, {"cancelled": True})
    except Exception as exc:
        events.emit(events.SYNC_DONE, {"error": str(exc)})
    finally:
        _status["running"] = False
        _cancel.clear()


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/run")
def sync_run():
    """Trigger Box→Local sync in the background. Logs emitted via SocketIO."""
    if _status["running"]:
        return {"status": "already_running"}
    threading.Thread(target=_sync_thread, daemon=True).start()
    return {"status": "started"}


@router.post("/cancel")
def sync_cancel():
    """Request cancellation of an in-progress sync."""
    if not _status["running"]:
        return {"status": "not_running"}
    _cancel.set()
    return {"status": "cancelling"}


@router.get("/status")
def sync_status():
    return {"running": _status["running"], "last": _status["last"]}
