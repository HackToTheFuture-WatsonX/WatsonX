"""
extractor.py — PDF extraction pipeline for PDF Extractor V3.
Ported from ExtractFrame._do_extraction (pdf_extractor_ui_v2.py lines 1655–1849).

NOTE: pdf_text_extractor is imported directly (not via importlib) so that
PyInstaller can statically resolve all dependencies for the portable .exe build.
"""
import sys
import threading
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter
from config import (
    BASE_DIR, read_config,
    extracted_folder, archive_folder,
)
from tracking import load_tracking, save_tracking
from box_client import get_box_client, upload_file_to_box
import events

router = APIRouter(prefix="/api/extract", tags=["extract"])

# Shared run-state so the frontend can rehydrate after navigating away.
_status = {"running": False, "last": None}
_cancel = threading.Event()


def _emit(event: str, data):
    events.emit(event, data)



def build_extract_folder(base_dir: Path, when: datetime) -> Path:
    week_num = when.isocalendar()[1]
    folder   = (
        base_dir
        / str(when.year)
        / f"{when.strftime('%b_%Y')}_Extracts"
        / f"Week_{week_num:02d}"
        / when.strftime("%Y-%m-%d")
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_extraction_log(ref_number: str, when: datetime, content: str) -> int:
    """Persist an extraction log entry to the database (single source of truth).
    Returns the new log row id."""
    import db
    safe_ref = (ref_number or "").strip() or "UNKNOWN_REF"
    return db.log_add(safe_ref, when, content)



def _load_extractor():
    """
    Import pdf_text_extractor as a module.
    - In a PyInstaller frozen bundle, BASE_DIR is the _MEIPASS temp directory
      and pdf_text_extractor is a compiled .pyc — standard import works.
    - In development, we ensure BASE_DIR is on sys.path then import directly.
    """
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    import pdf_text_extractor as _pte  # noqa: PLC0415
    return _pte


def run_extraction() -> list[dict]:
    """Full extraction pipeline. Emits SocketIO progress/result events."""
    extractor = _load_extractor()
    cfg              = read_config()
    password         = cfg.get("pdf_password", "")
    output_folder_id = cfg.get("box", {}).get("output_folder_id", "")
    ext_root         = extracted_folder()
    word_root        = ext_root / "Word Extracts"
    csv_root         = ext_root / "CSV Extracts"
    json_root        = ext_root / "JSON File Extracts"
    arch_root        = archive_folder()
    for d in (word_root, csv_root, json_root, arch_root):
        d.mkdir(parents=True, exist_ok=True)

    db      = load_tracking()
    pending = {k: v for k, v in db.get("files", {}).items()
               if v.get("status", "Pending") == "Pending"}

    if not pending:
        _emit(events.EXTRACT_DONE, {"completed": 0, "failed": 0, "total": 0})
        return []

    box_client = None
    if output_folder_id and not output_folder_id.startswith("YOUR_"):
        try:
            box_client, _ = get_box_client()
        except Exception:
            pass

    now     = datetime.now()
    results = []
    total   = len(pending)

    for idx, (rel_key, info) in enumerate(pending.items(), 1):
        if _cancel.is_set():
            break
        fname      = info.get("name", rel_key)
        local_path = Path(info.get("local_path", ""))

        if not local_path.exists():
            from config import local_folder as _lf
            local_path = _lf() / rel_key

        _emit(events.EXTRACT_PROGRESS, {
            "current": idx, "total": total,
            "percent": round(idx / total * 100),
            "name": fname,
        })

        try:
            with open(local_path, "rb") as fh:
                pdf_bytes = fh.read()

            doc        = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
            pages      = extractor.extract_text_by_page(doc)
            doc.close()
            structured = extractor.build_structured_json(fname, pages)
            ref_number = (
                structured.get("report_summary", {}).get("case_reference", "").strip()
                or Path(fname).stem
            )

            daily_word = build_extract_folder(word_root, now)
            daily_csv  = build_extract_folder(csv_root,  now)
            daily_json = build_extract_folder(json_root, now)

            orig = extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR
            extractor.WORD_OUT_DIR = daily_word
            extractor.CSV_OUT_DIR  = daily_csv
            extractor.JSON_OUT_DIR = daily_json
            try:
                word_path = extractor.export_to_word(fname, structured, ref_number, False)
                csv_path  = extractor.export_to_csv( fname, structured, ref_number, False)
                json_path = extractor.export_to_json(fname, structured, ref_number, False)
            finally:
                extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = orig

            upload_status = ""
            if box_client and output_folder_id:
                try:
                    for op in (word_path, csv_path, json_path):
                        upload_file_to_box(op, output_folder_id, box_client,
                                           extracted_root=ext_root)
                    upload_status = f"Uploaded to Box folder {output_folder_id}"
                except Exception as ue:
                    upload_status = f"Upload failed: {str(ue)[:120]}"
            else:
                upload_status = "Box upload not configured"

            archive_dest = arch_root / fname
            if archive_dest.exists():
                stem   = Path(fname).stem
                suffix = Path(fname).suffix
                archive_dest = arch_root / f"{stem}_{now.strftime('%Y%m%d%H%M%S')}{suffix}"
            try:
                shutil.move(str(local_path), str(archive_dest))
            except Exception:
                archive_dest = local_path

            db["files"][rel_key].update({
                "name":           fname,
                "status":         "Completed",
                "last_extracted": now.isoformat(timespec="seconds"),
                "ref_number":     ref_number,
                "archive_path":   str(archive_dest),
            })

            log_content = "\n".join([
                "Background Check Report Automation V3 — Extraction Log",
                "=" * 60,
                f"File       : {fname}",
                f"Reference  : {ref_number}",
                f"Started    : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Completed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status     : Completed",
                "",
                "Outputs",
                "-" * 40,
                f"Word    : {word_path}",
                f"Excel   : {csv_path}",
                f"JSON    : {json_path}",
                f"Archive : {archive_dest}",
                "",
                f"Box Upload : {upload_status}",
            ])
            write_extraction_log(ref_number, now, log_content)

            result = {
                "status": "ok", "fname": fname, "ref": ref_number,
                "word": str(word_path), "excel": str(csv_path),
                "json": str(json_path), "upload": upload_status,
            }
            results.append(result)
            _emit(events.EXTRACT_RESULT, result)

        except Exception as exc:
            db["files"][rel_key].setdefault("status", "Pending")
            error_result = {"status": "error", "fname": fname, "error": str(exc)[:300]}
            results.append(error_result)
            _emit(events.EXTRACT_RESULT, error_result)
            write_extraction_log(
                Path(fname).stem, now,
                f"FAILED: {fname}\nError: {exc}"
            )

    save_tracking(db)
    completed = sum(1 for r in results if r.get("status") == "ok")
    failed    = sum(1 for r in results if r.get("status") == "error")
    done_payload = {"completed": completed, "failed": failed, "total": total}
    if _cancel.is_set():
        done_payload["cancelled"] = True
    _emit(events.EXTRACT_DONE, done_payload)
    return results


def _extract_thread():
    _status["running"] = True
    _cancel.clear()
    try:
        _status["last"] = run_extraction()
    finally:
        _status["running"] = False
        _cancel.clear()


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/run")
def extract_run():
    """Trigger extraction pipeline in the background."""
    if _status["running"]:
        return {"status": "already_running"}
    threading.Thread(target=_extract_thread, daemon=True).start()
    return {"status": "started"}


@router.post("/cancel")
def extract_cancel():
    """Request cancellation of an in-progress extraction."""
    if not _status["running"]:
        return {"status": "not_running"}
    _cancel.set()
    return {"status": "cancelling"}


@router.get("/status")
def extract_status():
    return {"running": _status["running"], "last": _status["last"]}


@router.get("/results")
def extract_results():
    """Return current tracking DB with full file details."""
    from scanner import scan_files
    return scan_files()

