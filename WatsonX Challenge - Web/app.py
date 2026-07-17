"""
Background Check Report Automation — Web Application
======================================================
Flask web server that mirrors every feature of the desktop app:

  /              → Home (dashboard cards)
  /check         → Check Box Folder (scan + file table)
  /insights      → Insights (statistics chart data)
  /extract       → Extract Files (run pipeline)
  /chat          → AI Assistant (watsonx Orchestrate)

  POST /api/scan         — trigger Box scan
  POST /api/extract      — trigger full extraction pipeline
  GET  /api/status       — return tracking DB counts
  GET  /api/insights     — return chart bucket data
  POST /api/chat         — send message to watsonx Orchestrate
  GET  /api/logs         — return log history summary

watsonx Orchestrate Integration
---------------------------------
This app integrates with IBM watsonx Orchestrate via its REST API.
Orchestrate acts as the AI backbone for the /chat endpoint:
  1. User message arrives at POST /api/chat
  2. app.py calls the Orchestrate agent API with the message + context
  3. Orchestrate agent reasons, optionally calls skills, returns a reply
  4. Any [ACTION:*] tags trigger server-side actions before the reply is returned

Orchestrate Skills exposed by this app (callable by the agent):
  • scan_box_folder        — list PDFs in the configured Box folder
  • run_extraction         — run the full PDF extraction pipeline
  • lookup_report          — search extracted JSON reports by name / ref
  • get_log_history        — return extraction log history for a period
  • get_file_status        — return Pending / Completed counts

Configuration: all credentials live in config.json (same directory).
"""

import json
import threading
import importlib.util
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, send_file

# ─────────────────────────────────────────────────────────────────────────────
# Path constants
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.resolve()
CONFIG_PATH     = BASE_DIR / "config.json"
TRACKING_PATH   = BASE_DIR / "tracking_db.json"
LOG_HISTORY_DIR = BASE_DIR / "Log History"
JSON_DIR        = BASE_DIR / "JSON File Extracts"   # local cache — still used as temp write target

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# ─────────────────────────────────────────────────────────────────────────────
# Shared extraction lock — prevents overlapping pipeline runs
# ─────────────────────────────────────────────────────────────────────────────
_extract_lock   = threading.Lock()
_extract_running = False
_extract_result  = None   # stores the last extraction summary string


# ─────────────────────────────────────────────────────────────────────────────
# Config + tracking helpers
# ─────────────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tracking() -> dict:
    if TRACKING_PATH.exists():
        with open(TRACKING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}


def save_tracking(db: dict) -> None:
    with open(TRACKING_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Box output helpers — upload to / read from the output Box folder
# ─────────────────────────────────────────────────────────────────────────────

def _get_box_client():
    """Return an authenticated Box client using the JWT config in config.json."""
    extractor = _load_extractor.__wrapped__ if hasattr(_load_extractor, "__wrapped__") else None
    # We need the extractor only for get_box_client — import boxsdk directly here
    # so this helper is usable before _load_extractor is called.
    cfg     = load_config()
    box_cfg = cfg.get("box", {})

    from boxsdk import JWTAuth, Client as BoxClient
    jwt_filename = box_cfg.get("jwt_config_file", "box_jwt_config.json")
    candidates = [
        BASE_DIR / jwt_filename,
        BASE_DIR.parent / "PDF Extractor" / jwt_filename,
    ]
    jwt_path = next((p.resolve() for p in candidates if p.exists()), None)
    if jwt_path is None:
        raise FileNotFoundError(f"Box JWT config '{jwt_filename}' not found.")
    auth   = JWTAuth.from_settings_file(str(jwt_path))
    return BoxClient(auth), box_cfg


def _box_upload_file(local_path: Path, box_folder_id: str) -> str:
    """
    Upload a local file to the given Box folder, overwriting any existing file
    with the same name (Box versioning keeps the history automatically).

    Returns the Box file ID of the uploaded file.
    """
    client, _ = _get_box_client()
    folder    = client.folder(box_folder_id)

    # Check for an existing file with the same name to upload a new version
    existing_id = None
    try:
        items = folder.get_items(limit=1000)
        for item in items:
            if item.type == "file" and item.name == local_path.name:
                existing_id = item.id
                break
    except Exception:
        pass

    with open(local_path, "rb") as fh:
        if existing_id:
            box_file = client.file(existing_id).update_contents(fh)
        else:
            box_file = folder.upload_stream(fh, local_path.name)

    return box_file.id


def _box_get_or_create_subfolder(client, parent_folder_id: str, name: str) -> str:
    """
    Return the Box folder ID of a subfolder named `name` inside `parent_folder_id`.
    Creates the subfolder if it does not exist. Raises on failure.
    """
    # List existing children to find the subfolder
    items = client.folder(parent_folder_id).get_items(limit=1000)
    for item in items:
        if item.type == "folder" and item.name == name:
            return item.id
    # Not found — create it
    new_folder = client.folder(parent_folder_id).create_subfolder(name)
    return new_folder.id


def _box_upload_to_dated_path(local_path: Path, output_folder_id: str,
                               ref_number: str, when: datetime,
                               client=None) -> str:
    """
    Upload local_path into a dated sub-folder structure on Box mirroring the
    local layout:  <year>/<Mon_YYYY>_Extracts/Week_NN/<YYYY-MM-DD>/<ref>/

    Accepts an optional pre-authenticated `client` to avoid re-authenticating
    on every call. Returns the Box file ID.
    """
    if client is None:
        client, _ = _get_box_client()

    year_name  = str(when.year)
    month_name = f"{when.strftime('%b_%Y')}_Extracts"
    week_name  = f"Week_{when.isocalendar()[1]:02d}"
    day_name   = when.strftime("%Y-%m-%d")
    safe_ref   = re.sub(r'[<>:"/\\|?*]', "_", ref_number).strip() or "UNKNOWN_REF"

    folder_id = output_folder_id
    for segment in (year_name, month_name, week_name, day_name, safe_ref):
        folder_id = _box_get_or_create_subfolder(client, folder_id, segment)

    # Upload the file — update existing version or create new
    existing_id = None
    items = client.folder(folder_id).get_items(limit=1000)
    for item in items:
        if item.type == "file" and item.name == local_path.name:
            existing_id = item.id
            break

    with open(local_path, "rb") as fh:
        if existing_id:
            box_file = client.file(existing_id).update_contents(fh)
        else:
            box_file = client.folder(folder_id).upload_stream(fh, local_path.name)

    return box_file.id


def _box_download_json_files(output_folder_id: str) -> list[dict]:
    """
    Recursively walk the Box output folder and return a list of parsed JSON
    dicts for every .json file found.  Used by skill_lookup_report() so that
    lookups always read the authoritative copy on Box.
    """
    client, _ = _get_box_client()
    results = []

    def _walk(folder_id: str):
        try:
            items = client.folder(folder_id).get_items(limit=1000)
        except Exception:
            return
        for item in items:
            if item.type == "file" and item.name.lower().endswith(".json"):
                try:
                    content = client.file(item.id).content()
                    report  = json.loads(content.decode("utf-8"))
                    results.append(report)
                except Exception:
                    pass
            elif item.type == "folder":
                _walk(item.id)

    _walk(output_folder_id)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Extractor module loader — imports pdf_text_extractor.py at runtime.
# The extractor lives in the sibling "PDF Extractor" folder so both apps
# share the same parsing / export logic without duplication.
# ─────────────────────────────────────────────────────────────────────────────
def _load_extractor():
    extractor_path = BASE_DIR.parent / "PDF Extractor" / "pdf_text_extractor.py"
    spec      = importlib.util.spec_from_file_location("pdf_text_extractor", extractor_path)
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    # Point output dirs at this web app's own folders
    extractor.WORD_OUT_DIR = BASE_DIR / "Word Extracts"
    extractor.CSV_OUT_DIR  = BASE_DIR / "CSV Extracts"
    extractor.JSON_OUT_DIR = BASE_DIR / "JSON File Extracts"
    return extractor


# ─────────────────────────────────────────────────────────────────────────────
# Log helpers
# ─────────────────────────────────────────────────────────────────────────────
def build_extract_folder(base_dir: Path, when: datetime) -> Path:
    year_folder   = base_dir / str(when.year)
    month_folder  = year_folder / f"{when.strftime('%b_%Y')}_Extracts"
    week_num      = when.isocalendar()[1]
    weekly_folder = month_folder / f"Week_{week_num:02d}"
    daily_folder  = weekly_folder / when.strftime("%Y-%m-%d")
    daily_folder.mkdir(parents=True, exist_ok=True)
    return daily_folder


def write_extraction_log(ref_number: str, when: datetime, content: str) -> Path:
    year_folder  = LOG_HISTORY_DIR / str(when.year)
    month_folder = year_folder     / when.strftime("%b_%Y")
    week_num     = when.isocalendar()[1]
    week_folder  = month_folder    / f"Week_{week_num:02d}"
    day_folder   = week_folder     / when.strftime("%Y-%m-%d")
    day_folder.mkdir(parents=True, exist_ok=True)
    safe_ref  = re.sub(r'[<>:"/\\|?*]', "_", ref_number).strip() or "UNKNOWN_REF"
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    log_path  = day_folder / f"{safe_ref}_{timestamp}.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return log_path


# ─────────────────────────────────────────────────────────────────────────────
# ── Skills (callable by watsonx Orchestrate agent) ───────────────────────────
# Each function is a self-contained unit of work that returns a plain string.
# The Orchestrate agent calls these via the REST skill endpoints defined below.
# ─────────────────────────────────────────────────────────────────────────────

def skill_scan_box_folder() -> str:
    """Scan the Box source folder and update the tracking DB. Returns a summary."""
    try:
        extractor = _load_extractor()
        cfg       = extractor.load_config()
        box_cfg   = cfg.get("box", {})
        folder_id = box_cfg.get("folder_id", "0")
        search_sub = cfg.get("settings", {}).get("search_subfolders", True)
        client    = extractor.get_box_client(box_cfg)
        pdf_files = extractor.find_pdf_files_on_box(client, folder_id, search_sub)

        db = load_tracking()
        for f in pdf_files:
            existing = db["files"].get(f["id"], {})
            db["files"][f["id"]] = {
                "name":           f["name"],
                "status":         "Pending",
                "last_extracted": existing.get("last_extracted"),
                "ref_number":     existing.get("ref_number"),
                "archived":       False,
            }
        save_tracking(db)
        return f"Scan complete. Found {len(pdf_files)} PDF file(s) in Box folder."
    except Exception as exc:
        return f"Scan failed: {exc}"


def skill_run_extraction() -> str:
    """Run the full PDF extraction pipeline. Returns a plain-text result summary."""
    global _extract_running, _extract_result
    if _extract_running:
        return "Extraction is already running. Please wait for it to finish."

    _extract_running = True
    results = []
    try:
        extractor = _load_extractor()
        cfg       = extractor.load_config()
        password  = cfg.get("pdf_password", "")
        box_cfg   = cfg.get("box", {})
        folder_id = box_cfg.get("folder_id", "0")
        archive_id = box_cfg.get("archive_folder_id", "")
        search_sub = cfg.get("settings", {}).get("search_subfolders", True)

        client    = extractor.get_box_client(box_cfg)
        pdf_files = extractor.find_pdf_files_on_box(client, folder_id, search_sub)

        if not pdf_files:
            return "No PDF files found in the Box source folder."

        db  = load_tracking()
        now = datetime.now()

        # Read output_folder_id from the web app's own config.json — NOT from
        # extractor.load_config() which reads PDF Extractor/config.json and has
        # no output_folder_id field (root cause of Box upload never firing).
        output_folder_id = load_config().get("box", {}).get("output_folder_id", "")

        for box_file in pdf_files:
            fid   = box_file["id"]
            fname = box_file["name"]
            try:
                pdf_bytes  = extractor.download_pdf_bytes(client, fid, fname)
                doc        = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
                pages      = extractor.extract_text_by_page(doc)
                doc.close()
                structured = extractor.build_structured_json(fname, pages)

                ref_number = (
                    structured.get("report_summary", {}).get("case_reference", "").strip()
                    or Path(fname).stem
                )

                # ── Export directly to local dated folders ────────────────────
                # Files are always written locally first (permanent local copy).
                # Then also uploaded to Box output folder if configured.
                # No temp dir, no archiving — simplest and safest.
                box_word_id = box_csv_id = box_json_id = ""
                upload_errors = []

                daily_word = build_extract_folder(BASE_DIR / "Word Extracts", now)
                daily_csv  = build_extract_folder(BASE_DIR / "CSV Extracts",  now)
                daily_json = build_extract_folder(BASE_DIR / "JSON File Extracts", now)

                extractor.WORD_OUT_DIR = daily_word
                extractor.CSV_OUT_DIR  = daily_csv
                extractor.JSON_OUT_DIR = daily_json
                try:
                    word_path = extractor.export_to_word(fname, structured, ref_number, False)
                    csv_path  = extractor.export_to_csv(fname, structured, ref_number, False)
                    json_path = extractor.export_to_json(fname, structured, ref_number, False)
                finally:
                    extractor.WORD_OUT_DIR = BASE_DIR / "Word Extracts"
                    extractor.CSV_OUT_DIR  = BASE_DIR / "CSV Extracts"
                    extractor.JSON_OUT_DIR = BASE_DIR / "JSON File Extracts"

                # ── Also upload to Box if output_folder_id is configured ──────
                if output_folder_id:
                    try:
                        _upload_client, _ = _get_box_client()
                    except BaseException as e:
                        _err = f"Box auth failed: {type(e).__name__}: {e}"
                        upload_errors.append(_err)
                        print(f"[BOX UPLOAD] {_err}", flush=True)
                        _upload_client = None

                    if _upload_client:
                        try:
                            box_word_id = _box_upload_to_dated_path(
                                word_path, output_folder_id, ref_number, now, _upload_client)
                        except BaseException as e:
                            _err = f"Word Box upload failed: {type(e).__name__}: {e}"
                            upload_errors.append(_err)
                            print(f"[BOX UPLOAD] {_err}", flush=True)
                        try:
                            box_csv_id = _box_upload_to_dated_path(
                                csv_path, output_folder_id, ref_number, now, _upload_client)
                        except BaseException as e:
                            _err = f"Excel Box upload failed: {type(e).__name__}: {e}"
                            upload_errors.append(_err)
                            print(f"[BOX UPLOAD] {_err}", flush=True)
                        try:
                            box_json_id = _box_upload_to_dated_path(
                                json_path, output_folder_id, ref_number, now, _upload_client)
                        except BaseException as e:
                            _err = f"JSON Box upload failed: {type(e).__name__}: {e}"
                            upload_errors.append(_err)
                            print(f"[BOX UPLOAD] {_err}", flush=True)

                # ── Archive source PDF on Box if archive_folder_id is set ────────
                # Move the source file from the source folder into the archive
                # folder so it is not re-processed on the next extraction run.
                archived   = False
                archive_err = ""
                if archive_id:
                    try:
                        dest_folder = client.folder(archive_id)
                        client.file(fid).move(dest_folder)
                        archived = True
                        print(f"[ARCHIVE] '{fname}' moved to archive folder {archive_id}", flush=True)
                    except Exception as ae:
                        archive_err = f"Archive failed: {type(ae).__name__}: {ae}"
                        print(f"[ARCHIVE] {archive_err}", flush=True)

                db["files"][fid] = db["files"].get(fid, {})
                db["files"][fid].update({
                    "name": fname, "status": "Completed",
                    "last_extracted": now.isoformat(timespec="seconds"),
                    "ref_number": ref_number, "archived": archived,
                    "box_json_id": box_json_id,
                })

                log_content = "\n".join([
                    "Background Check Report Automation — Extraction Log",
                    "=" * 60,
                    f"File       : {fname}",
                    f"Reference  : {ref_number}",
                    f"Completed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Status     : Completed",
                    f"Archived   : {'Yes — moved to folder ' + archive_id if archived else ('No — ' + archive_err if archive_err else 'No (archive_folder_id not set)')}",
                    "", "Box Upload", "-" * 40,
                    f"Word (Box ID)  : {box_word_id  or 'FAILED — saved locally'}",
                    f"Excel (Box ID) : {box_csv_id   or 'FAILED — saved locally'}",
                    f"JSON (Box ID)  : {box_json_id  or 'FAILED — saved locally'}",
                    *(["", "Upload Errors", "-" * 40] + upload_errors if upload_errors else []),
                ])
                write_extraction_log(ref_number, now, log_content)
                results.append(f"✅ {fname} → Ref: {ref_number}{' (archived)' if archived else ''}")

            except Exception as exc:
                db["files"].setdefault(fid, {"name": fname, "status": "Pending"})
                log_content = "\n".join([
                    "Background Check Report Automation — Extraction Log",
                    "=" * 60,
                    f"File    : {fname}",
                    f"Failed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Status  : FAILED",
                    "", "Error", "-" * 40,
                    str(exc),
                ])
                write_extraction_log(Path(fname).stem, now, log_content)
                results.append(f"❌ {fname} → Error: {str(exc)[:200]}")

        save_tracking(db)
        completed = sum(1 for r in results if r.startswith("✅"))
        failed    = sum(1 for r in results if r.startswith("❌"))
        summary   = (
            f"Extraction complete. Processed {len(pdf_files)} file(s): "
            f"{completed} succeeded, {failed} failed.\n\n" + "\n".join(results)
        )
        _extract_result = summary
        return summary

    except Exception as exc:
        return f"Extraction pipeline error: {exc}"
    finally:
        _extract_running = False


# Status emoji helpers used by the rich report formatter
_STATUS_EMOJI = {
    "cleared": "✅", "verified": "✅", "pass": "✅", "passed": "✅",
    "clear": "✅",
    "failed": "❌", "fail": "❌", "unverified": "❌", "adverse": "❌",
    "--": "⬜", "": "⬜",
}

def _status_icon(val: str) -> str:
    """Return an emoji for a status/result value."""
    v = (val or "").strip().lower()
    for key, icon in _STATUS_EMOJI.items():
        if key and key in v:
            return icon
    return "🔵"


def skill_lookup_report(query: str) -> str:
    """Search extracted JSON reports by subject name or case reference.

    • Multiple records with the SAME case reference → only the latest version
      (by extracted_at) is kept — deduplication within one case.
    • Multiple records with DIFFERENT case references that match the query
      (e.g. "Reyes, Jeffrey" and "Reyes, Mary") → ALL are returned, up to 5.
    Returns rich-formatted text with §SECTION§ markers for the frontend renderer.
    """
    if not query.strip():
        return "Please provide a name or reference number to search for."

    q_lower = query.strip().lower()

    # ── Collect all matching reports, keyed by case_reference ────────────────
    # best_by_ref: { case_reference_lower → report_dict with highest extracted_at }
    # This keeps one (latest) version per ref while allowing MULTIPLE different refs.
    best_by_ref: dict = {}

    def _ingest_report(report: dict):
        s    = report.get("report_summary", {})
        name = s.get("subject_name", "").lower()
        ref  = s.get("case_reference", "").lower()
        # Match if query appears anywhere in name OR reference number
        if q_lower not in name and q_lower not in ref:
            return
        existing = best_by_ref.get(ref)
        if existing is None:
            best_by_ref[ref] = report
        else:
            new_ts = report.get("extracted_at", "")
            old_ts = existing.get("extracted_at", "")
            if new_ts > old_ts:
                best_by_ref[ref] = report

    # ── Primary source: Box output folder ────────────────────────────────────
    _box_contacted = False
    cfg = load_config()
    output_folder_id = cfg.get("box", {}).get("output_folder_id", "")
    if output_folder_id:
        try:
            for report in _box_download_json_files(output_folder_id):
                _ingest_report(report)
            _box_contacted = True
        except Exception:
            pass

    # ── Fallback: local JSON_DIR ──────────────────────────────────────────────
    if not _box_contacted and JSON_DIR.exists():
        for json_path in JSON_DIR.rglob("*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as fh:
                    _ingest_report(json.load(fh))
            except Exception:
                continue

    if not best_by_ref:
        return f"No reports found matching '{query}'."

    matches = list(best_by_ref.values())

    # ── If multiple distinct people match, show a summary list first ──────────
    # e.g. searching "Reyes" returns Reyes Jeffrey, Reyes Mary, Reyes Justin
    multi_header = ""
    if len(matches) > 1:
        multi_header = (
            f"§MULTI_HEADER§Found {len(matches)} record(s) matching '{query}':\n"
            + "\n".join(
                f"  • {r.get('report_summary',{}).get('subject_name','--')} "
                f"— Ref: {r.get('report_summary',{}).get('case_reference','--')}"
                for r in matches[:5]
            )
            + "\n§END_MULTI_HEADER§\n"
        )

    OTHER_CHECK_ORDER = [
        "Adverse Media Check",
        "Global Sanctions",
        "Bankruptcy Check",
        "Financial/Credit Check",
        "Directorship Check",
        "Civil Litigation Check",
        "Professional License Qualification",
        "Social Media Screening",
    ]

    # Icons for the database check categories
    OTHER_CHECK_ICON = {
        "Adverse Media Check":              "📰",
        "Global Sanctions":                 "🌐",
        "Bankruptcy Check":                 "🏦",
        "Financial/Credit Check":           "💳",
        "Directorship Check":               "🏢",
        "Civil Litigation Check":           "⚖️",
        "Professional License Qualification":"🎓",
        "Social Media Screening":           "📱",
    }

    blocks = []
    for r in matches[:5]:
        s = r.get("report_summary", {})
        subject  = s.get("subject_name", "--")
        ref_num  = s.get("case_reference", "--")
        delivery = s.get("delivery_date", "--")
        received = s.get("case_received", "")
        package  = s.get("package", "")
        overall  = s.get("overall_status", "--")
        overall_icon = _status_icon(overall)

        lines = []

        # ── Report card header ────────────────────────────────────────────────
        lines.append(f"§REPORT_HEADER§")
        lines.append(f"Subject: {subject} | Ref: {ref_num} | Delivery: {delivery}")
        if received and received.strip():
            lines.append(f"Case Received: {received}")
        if package and package.strip():
            lines.append(f"Package: {package}")
        lines.append(f"§END_REPORT_HEADER§")

        # ── Overall Status banner ─────────────────────────────────────────────
        lines.append(f"§STATUS_BANNER§{overall_icon} Overall Status: {overall}§END_STATUS_BANNER§")

        # ── Employment checks ─────────────────────────────────────────────────
        emp_checks = r.get("employment_checks", [])
        if emp_checks:
            lines.append(f"§SECTION_HEADER§💼 Employment Verification§END_SECTION_HEADER§")
            for ec in emp_checks:
                emp_status = ec.get("verification_status", "--")
                emp_icon   = _status_icon(emp_status)
                lines.append(
                    f"§SUBSECTION§{emp_icon} Employment {ec.get('check_number','?')}: "
                    f"{ec.get('employer_name','--')} — {emp_status}§END_SUBSECTION§"
                )
                for label, key in [
                    ("Position",            "position_title"),
                    ("Address",             "company_address"),
                    ("Dates",               "dates_of_employment"),
                    ("Employment Status",   "status_of_employment"),
                    ("Reason for Exit",     "reason_for_exit"),
                    ("Eligible for Rehire", "eligible_for_rehire"),
                    ("Respondent",          "respondents_name"),
                    ("Respondent Title",    "respondents_title"),
                    ("Contact",             "contact_details"),
                    ("Verification Date",   "verification_date"),
                    ("Result",              "result"),
                    ("Notes",               "notes"),
                ]:
                    val = ec.get(key, "")
                    if val and str(val).strip():
                        lines.append(f"§FIELD§{label}§SEP§{val}§END_FIELD§")

        # ── Professional reference checks ─────────────────────────────────────
        ref_checks = r.get("professional_reference_checks", [])
        if ref_checks:
            lines.append(f"§SECTION_HEADER§🤝 Professional References§END_SECTION_HEADER§")
            for pr in ref_checks:
                ref_status = pr.get("verification_status", "--")
                ref_icon   = _status_icon(ref_status)
                lines.append(
                    f"§SUBSECTION§{ref_icon} Reference {pr.get('check_number','?')}: "
                    f"{pr.get('referee_name','--')} — {ref_status}§END_SUBSECTION§"
                )
                for label, key in [
                    ("Result",           "result"),
                    ("Verifier Name",    "verifiers_name"),
                    ("Verifier Contact", "verifiers_contact"),
                    ("Notes",            "notes"),
                ]:
                    val = pr.get(key, "")
                    if val and str(val).strip() and str(val).strip() != "-":
                        lines.append(f"§FIELD§{label}§SEP§{val}§END_FIELD§")
                for qa in pr.get("qa", []):
                    answer   = qa.get("answer", "").strip()
                    question = qa.get("question", "").strip()
                    if answer and question:
                        lines.append(f"§FIELD§Q§SEP§{question}§END_FIELD§")
                        lines.append(f"§FIELD§A§SEP§{answer}§END_FIELD§")

        # ── Database checks ───────────────────────────────────────────────────
        other_map = {
            oc.get("check_name", "").strip().lower(): oc
            for oc in r.get("other_checks", [])
        }
        lines.append(f"§SECTION_HEADER§🗂️ Database Checks§END_SECTION_HEADER§")
        for check_name in OTHER_CHECK_ORDER:
            oc     = next((v for k, v in other_map.items() if k == check_name.lower()), {})
            status = oc.get("status", "--") if oc else "--"
            icon   = OTHER_CHECK_ICON.get(check_name, "🔵")
            chk_icon = _status_icon(status)
            lines.append(
                f"§DB_CHECK§{icon} {check_name}§SEP§{chk_icon} {status}§END_DB_CHECK§"
            )
            result_val = oc.get("result", "") if oc else ""
            source_val = oc.get("source", "") if oc else ""
            if result_val and str(result_val).strip():
                lines.append(f"§FIELD§Result§SEP§{result_val}§END_FIELD§")
            if source_val and str(source_val).strip():
                lines.append(f"§FIELD§Source§SEP§{source_val}§END_FIELD§")

        lines.append("§REPORT_END§")
        blocks.append("\n".join(lines))

    return multi_header + "\n\n".join(blocks)


def skill_get_log_history(period: str = "day") -> str:
    """Return a plain-text summary of extraction logs for the given period."""
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
        except ValueError:
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
            with open(log_path, "r", encoding="utf-8") as fh:
                content_lines = fh.read().splitlines()
            lines.append("\n".join(f"  {l}" for l in content_lines[:10]))
            if len(content_lines) > 10:
                lines.append(f"  … ({len(content_lines) - 10} more lines)")
        except Exception:
            lines.append("  (could not read log file)")
    lines.append("\n=== END LOG HISTORY ===")
    return "\n".join(lines)


def skill_get_file_status() -> str:
    """Return current Pending / Completed file counts."""
    db        = load_tracking()
    files     = db.get("files", {})
    total     = len(files)
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    pending   = total - completed
    return (
        f"File Status Summary:\n"
        f"  Total     : {total}\n"
        f"  Completed : {completed}\n"
        f"  Pending   : {pending}"
    )


def skill_generate_reports(query: str = "") -> str:
    """
    Find extracted report files (Word .docx, Excel .xlsx, JSON .json) for a
    given subject name, reference number, or time period and return download links.

    Strategy:
      1. If query matches a ref number pattern (RN-…) → search files by ref directly.
      2. Otherwise resolve query → ref number(s) via the JSON records index, then
         search files by each resolved ref. Falls back to raw filename search.
      3. If query looks like a time period (month/week/year) → filter by folder path.
    """
    q = query.strip()
    if not q:
        return (
            "Which report would you like to download?\n"
            "Please specify a **name** (e.g. 'generate reports for Manalo') "
            "or a **reference number** (e.g. 'reports for RN-123456'), "
            "or tell me the **month/week/year** (e.g. 'reports for July 2026')."
        )

    q_lower = q.lower()

    EXTRACT_DIRS = [
        (BASE_DIR / "Word Extracts",      "📄 Word (.docx)"),
        (BASE_DIR / "CSV Extracts",       "📊 Excel (.xlsx)"),
        (BASE_DIR / "JSON File Extracts", "📋 JSON (.json)"),
    ]

    def _collect_files(match_fn) -> list[tuple[str, Path, str]]:
        """Walk all extract dirs; yield (label, path, url) where match_fn(path) is True."""
        hits = []
        for root_dir, type_label in EXTRACT_DIRS:
            if not root_dir.exists():
                continue
            for fpath in sorted(root_dir.rglob("*")):
                if fpath.is_file() and match_fn(fpath):
                    try:
                        rel = fpath.relative_to(BASE_DIR)
                    except ValueError:
                        rel = fpath
                    # URL-encode spaces in path segments
                    import urllib.parse
                    rel_url = "/api/download/" + "/".join(
                        urllib.parse.quote(p, safe="") for p in rel.parts
                    )
                    hits.append((type_label, fpath, rel_url))
        return hits

    # ── Step 1: Resolve name → ref number(s) via JSON index ─────────────────
    # Files are named by ref (e.g. RN-123456_789_10_v3.docx) so we must look
    # up which ref belongs to this person name before searching the filesystem.
    resolved_refs: set[str] = set()

    # If query already looks like a ref number, use it directly
    if re.match(r"rn[-_]?\d", q_lower):
        resolved_refs.add(re.sub(r"[^a-z0-9_\-]", "", q_lower))
    else:
        # Walk local JSON files to resolve name → case_reference
        if JSON_DIR.exists():
            for jp in JSON_DIR.rglob("*.json"):
                try:
                    data = json.loads(jp.read_text(encoding="utf-8"))
                    s    = data.get("report_summary", {})
                    name = s.get("subject_name", "").lower()
                    ref  = s.get("case_reference", "").lower()
                    if q_lower in name or q_lower in ref:
                        resolved_refs.add(ref.lower())
                except Exception:
                    continue

    # ── Step 2: Search files ─────────────────────────────────────────────────
    found: list[tuple[str, Path, str]] = []

    if resolved_refs:
        # Match files whose parent folder name OR stem contains any resolved ref
        def _by_ref(fpath: Path) -> bool:
            stem_lower   = fpath.stem.lower()
            folder_lower = fpath.parent.name.lower()
            return any(ref in stem_lower or ref in folder_lower for ref in resolved_refs)
        found = _collect_files(_by_ref)
    else:
        # Fallback: time-period / path search (e.g. "july 2026", "week 28", "2026", "Year 2026")
        # Strip noise words, then truncate month names to 3 chars (folders use "Jul_2026_Extracts")
        _noise = re.compile(
            r"\b(?:year|month|week|for|in|of|the|reports?|extracts?)\b",
            re.IGNORECASE,
        )
        _MONTH_FULL = re.compile(
            r"\b(january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\b",
            re.IGNORECASE,
        )
        _q_norm = _noise.sub(" ", q_lower)
        # Shorten month names to first 3 chars so "july" → "jul" matches "Jul_2026_Extracts"
        _q_norm = _MONTH_FULL.sub(lambda mo: mo.group(1)[:3].lower(), _q_norm)
        _tokens = [t for t in _q_norm.split() if t.strip()]

        def _by_path(fpath: Path) -> bool:
            path_lower = str(fpath).lower()
            # Every token must appear somewhere in the path
            return bool(_tokens) and all(tok in path_lower for tok in _tokens)
        found = _collect_files(_by_path)

    if not found:
        hint = ""
        if resolved_refs:
            hint = f" (resolved refs: {', '.join(resolved_refs)})"
        return (
            f"No report files found for **'{q}'**{hint}.\n"
            "If the report hasn't been extracted yet, try **'run extraction'** first."
        )

    # ── Step 3: Group by ref folder and render download links ────────────────
    from collections import OrderedDict
    groups: dict[str, list] = OrderedDict()
    for label, fpath, rel_url in found[:30]:
        folder_key = fpath.parent.name  # e.g. "RN-123456_789_10"
        if folder_key not in groups:
            groups[folder_key] = []
        groups[folder_key].append((label, fpath.name, rel_url))

    # Describe who these reports belong to
    subject_label = q
    if resolved_refs and JSON_DIR.exists():
        # Try to get a friendly name from the first matched JSON
        for jp in JSON_DIR.rglob("*.json"):
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
                s    = data.get("report_summary", {})
                ref  = s.get("case_reference", "").lower()
                if ref in resolved_refs:
                    subject_label = s.get("subject_name", q)
                    break
            except Exception:
                continue

    lines = [f"Found **{len(found)}** report file(s) for **{subject_label}**:\n"]
    for folder_key, files in groups.items():
        lines.append(f"§SECTION_HEADER§📁 {folder_key}§END_SECTION_HEADER§")
        for label, fname, rel_url in files:
            lines.append(f"§DOWNLOAD§{label} — {fname}§SEP§{rel_url}§END_DOWNLOAD§")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# IBM Consulting Advantage (ICA) 1.0 chat integration
# ─────────────────────────────────────────────────────────────────────────────
def ica_chat(history: list[dict], user_message: str) -> str:
    """
    Send a conversation turn to IBM Consulting Advantage (ICA) 1.0 and return the reply.
    Uses urllib — no extra SDK required.

    ICA requires the FULL browser cookie string (not just ica_core_auth_proxy) because
    Akamai bot-detection cookies (bm_sz, bm_sv, _abck, ak_bmsc) are also validated.

    Credentials in config.json → ica:
      full_cookie — entire cookie header copied from DevTools → Request Headers → cookie
      team_id     — ICA team UUID
      team_name   — ICA team name (URL-encoded, e.g. Synapxe%20ODC)
      chat_id     — ICA chat thread UUID
      base_url    — https://servicesessentials.ibm.com/curatorai/services/chat/new-chat
    """
    import urllib.request
    import urllib.error

    cfg       = load_config()
    ic        = cfg.get("ica", {})
    cookie    = ic.get("full_cookie", "")
    team_id   = ic.get("team_id", "")
    team_name = ic.get("team_name", "")
    chat_id   = ic.get("chat_id", "")
    base_url  = ic.get("base_url", "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat").rstrip("/")

    if not cookie:
        raise ValueError("ICA full_cookie not configured in config.json → ica.full_cookie")
    if not team_id:
        raise ValueError("ICA team_id not configured in config.json → ica.team_id")
    if not chat_id:
        raise ValueError("ICA chat_id not configured in config.json → ica.chat_id")

    # ICA payload confirmed from browser DevTools Payload tab
    url = f"{base_url}/chats/{chat_id}/entries"
    payload = json.dumps({
        "chatId": chat_id,
        "type":   "PROMPT",
        "content": {
            "prompt":               user_message,
            "promptId":             "",
            "promptUuid":           "",
            "isIncludedInContext":  True,
            "sensitiveInformation": {"hasSensitiveInformation": False},
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "cookie":        cookie,
            "teamid":        team_id,
            "teamname":      team_name,
            "Content-Type":  "application/json",
            "Accept":        "application/json, text/plain, */*",
            "Origin":        "https://servicesessentials.ibm.com",
            "Referer":       f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            echo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ICA {e.code}: {error_body[:500]}")

    # POST returns the prompt echo — poll GET /entries until ANSWER arrives
    import time
    entry_id = echo.get("_id", "")
    base_headers = {
        "cookie":        cookie,
        "teamid":        team_id,
        "teamname":      team_name,
        "Accept":        "application/json, text/plain, */*",
        "Origin":        "https://servicesessentials.ibm.com",
        "Referer":       f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }
    # Poll GET /chats/{chat_id}/entries — find ANSWER whose promptEntryId matches our prompt _id
    poll_url = f"{base_url}/chats/{chat_id}/entries"
    for _ in range(30):  # up to 30 × 2s = 60s
        time.sleep(2)
        poll_req = urllib.request.Request(poll_url, headers=base_headers, method="GET")
        try:
            with urllib.request.urlopen(poll_req, timeout=30) as poll_resp:
                data = json.loads(poll_resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            continue
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        answers = [e for e in entries if e.get("type") == "ANSWER"]
        if answers:
            return str(answers[-1].get("content", {}).get("answer", "")).strip() or "(No response from ICA)"
    return "(ICA did not respond in time)"


# ─────────────────────────────────────────────────────────────────────────────
# IBM Granite chat integration (watsonx.ai)
# ─────────────────────────────────────────────────────────────────────────────
def granite_chat(history: list[dict], user_message: str) -> str:
    """
    Send a conversation turn to IBM watsonx.ai and return the reply from
    IBM Granite (ibm/granite-3-8b-instruct or any other Granite model).

    Uses the watsonx.ai OpenAI-compatible text generation endpoint:
      POST {service_url}/ml/v1/text/chat?version=2024-05-01

    Credentials in config.json → watsonx:
      api_key     — IBM Cloud IAM API key
      project_id  — watsonx.ai Project ID (from Manage → General in the UI)
      service_url — e.g. https://us-south.ml.cloud.ibm.com
      model       — e.g. ibm/granite-3-8b-instruct
    """
    import urllib.request
    import urllib.error

    cfg     = load_config()
    wx      = cfg.get("watsonx", {})
    api_key     = wx.get("api_key", "")
    project_id  = wx.get("project_id", "")
    service_url = wx.get("service_url", "https://us-south.ml.cloud.ibm.com").rstrip("/")
    model       = wx.get("model", "ibm/granite-3-8b-instruct")

    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError("watsonx.ai API key not configured in config.json → watsonx.api_key")
    if not project_id or project_id == "YOUR_WATSONX_PROJECT_ID":
        raise ValueError("watsonx.ai project_id not configured in config.json → watsonx.project_id")

    # ── Step 1: Exchange IBM Cloud API key for IAM Bearer token ──────────────
    token_req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token",
        data=f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(token_req, timeout=15) as resp:
        iam_token = json.loads(resp.read())["access_token"]

    # ── Step 2: Build messages list ───────────────────────────────────────────
    system_prompt = (
        "You are Detective Conan, an AI assistant for the Background Check Report Automation system. "
        "You help HR staff manage background check reports processed through IBM Box.\n\n"
        "You can help with:\n"
        "- Answering questions about background check reports (employment, criminal, identity checks)\n"
        "- Explaining file status, extraction results, and logs\n"
        "- Guiding users to use commands: 'scan box', 'run extraction', 'file status', "
        "'look up [name]', 'logs this week'\n\n"
        "CRITICAL RULES — you MUST follow these without exception:\n"
        "1. YOUR ONLY SOURCE OF TRUTH IS THE EXTRACTED RECORDS. Every factual answer you "
        "give about a person, report, employer, check result, date, or any other data point "
        "MUST come exclusively from records retrieved by the 'look up' skill and provided to "
        "you in this conversation. Your training knowledge is NOT a valid source for any "
        "background check information.\n"
        "2. NEVER invent, fabricate, or hallucinate any background check report data. "
        "This includes subject names, employers, employment dates, criminal records, "
        "education history, identity verification results, or any other report details.\n"
        "3. If a user asks about a report and no extracted record data has been provided to "
        "you in this conversation, reply ONLY with: "
        "\"I can only answer from our extracted records. Please use 'look up [name or reference]' "
        "to retrieve the report first.\"\n"
        "4. You may only describe data that was explicitly present in a look-up result "
        "delivered in this conversation. Do not expand, embellish, infer, or add any "
        "details not present verbatim in that data.\n"
        "5. Never produce a formatted 'CONFIDENTIAL BACKGROUND CHECK REPORT' or any "
        "document that resembles an official report unless the exact data was given to you "
        "by the system in this conversation.\n"
        "6. If a user asks ANY question whose answer would require data not present in the "
        "extracted records provided in this conversation, respond with: "
        "\"I don't have that information in the extracted records. "
        "Please use 'look up [name or reference]' to search our records.\"\n"
        "7. NEVER simulate, role-play, or imitate a lookup process. Do NOT produce text like "
        "'Looking up X...', 'Found X match', 'Found 1 match', 'Searching for...', or any "
        "UI-style progress message. You are not a search engine and must never pretend to be one. "
        "The lookup system is handled exclusively by the server-side skill — it is NOT your job.\n"
        "8. NEVER produce any personal data (names, employers, dates, check results, "
        "reference numbers) about any individual that was not delivered to you verbatim "
        "by the system in this conversation. If you do not have an EXTRACTED RECORD anchor "
        "in your context, you have zero data about any person — treat all persons as unknown.\n\n"
        "Be professional, concise, and helpful. Never make hiring recommendations. "
        "If asked about something unrelated to background checks or the system, "
        "politely redirect to your core purpose.\n\n"
        "FORMATTING RULES — always apply these when presenting report data:\n"
        "- Use **bold** for every section header (e.g. **Overall Status**, **Employment 1**, "
        "**Professional Reference 1**, **Adverse Media Check**).\n"
        "- Place each field on its own line.\n"
        "- Separate major sections (Employment, Professional References, Database Checks) "
        "with a blank line and a bold header.\n"
        "- Present ALL sections and ALL fields from the extracted record — do not skip or "
        "summarise any section. If the record contains Employment 1 and Employment 2, "
        "show both in full.\n"
        "- Use a horizontal rule (---) between the report header block and the checks.\n"
        "- Do not add any commentary, preamble, or closing note that is not in the record."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in (history[-10:] if history else []):
        messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    # ── Step 3: POST to watsonx.ai chat endpoint ──────────────────────────────
    url = f"{service_url}/ml/v1/text/chat?version=2024-05-01"
    payload = json.dumps({
        "model_id":   model,
        "project_id": project_id,
        "messages":   messages,
        "parameters": {
            "max_new_tokens": 4096,
            "temperature":    0.7,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {iam_token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"watsonx.ai API error {e.code}: {error_body[:400]}")

    # ── Step 4: Extract reply ─────────────────────────────────────────────────
    # Shape: {"choices": [{"message": {"content": "..."}}]}
    reply = ""
    choices = result.get("choices", [])
    if choices:
        reply = choices[0].get("message", {}).get("content", "").strip()
    if not reply:
        # Fallback shape: {"results": [{"generated_text": "..."}]}
        results_list = result.get("results", [])
        if results_list:
            reply = results_list[0].get("generated_text", "").strip()

    return reply if reply else "(No response from Granite)"


# ─────────────────────────────────────────────────────────────────────────────
# Watson Assistant chat integration
# ─────────────────────────────────────────────────────────────────────────────
def watson_assistant_chat(history: list[dict], user_message: str) -> str:
    """
    Send a conversation turn to IBM Watson Assistant v2 and return the reply.

    Uses the stateless message API so no session management is required:
      POST {service_url}/v2/assistants/{assistant_id}/messages?version={api_version}

    Credentials in config.json → watson_assistant:
      api_key      — IBM Cloud IAM API key (or service credential API key)
      service_url  — e.g. https://api.eu-de.assistant.watson.cloud.ibm.com
      assistant_id — Assistant ID from Settings → API Details inside WA
      api_version  — date string, e.g. 2023-06-15
    """
    import urllib.request
    import urllib.error
    import base64

    cfg = load_config()
    wa  = cfg.get("watson_assistant", {})

    api_key      = wa.get("api_key", "")
    service_url  = wa.get("service_url", "").rstrip("/")
    assistant_id = wa.get("assistant_id", "")
    api_version  = wa.get("api_version", "2023-06-15")

    if not api_key or api_key == "YOUR_WATSON_ASSISTANT_API_KEY":
        raise ValueError(
            "Watson Assistant API key is not configured.\n"
            "Edit config.json → watson_assistant.api_key, service_url, and assistant_id."
        )
    if not assistant_id or assistant_id == "YOUR_WATSON_ASSISTANT_ASSISTANT_ID":
        raise ValueError("Watson Assistant assistant_id is not set in config.json.")
    if not service_url or service_url == "YOUR_WATSON_ASSISTANT_SERVICE_URL":
        raise ValueError("Watson Assistant service_url is not set in config.json.")

    # ── Build context: pass last 10 turns as generic string context ───────────
    context_text = ""
    if history:
        context_lines = []
        for turn in history[-10:]:
            role    = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            context_lines.append(f"{role}: {content}")
        context_text = "\n".join(context_lines)

    payload = json.dumps({
        "input": {
            "message_type": "text",
            "text": user_message,
            "options": {"return_context": True},
        },
        **({"context": {"skills": {"main skill": {"user_defined": {"history": context_text}}}}}
           if context_text else {}),
    }).encode()

    # Watson Assistant uses HTTP Basic auth: username "apikey", password = api_key
    credentials = base64.b64encode(f"apikey:{api_key}".encode()).decode()

    url = f"{service_url}/v2/assistants/{assistant_id}/messages?version={api_version}"

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Watson Assistant API error {e.code}: {error_body[:400]}")

    # ── Extract reply from response generic array ─────────────────────────────
    reply_parts = []
    for generic in result.get("output", {}).get("generic", []):
        if generic.get("response_type") == "text":
            reply_parts.append(generic.get("text", ""))
    reply = "\n".join(reply_parts).strip()

    # ── Handle [ACTION:*] tags (same as Orchestrate) ──────────────────────────
    action_map = {
        "[ACTION:SCAN]":         skill_scan_box_folder,
        "[ACTION:EXTRACT_CHAT]": skill_run_extraction,
        "[ACTION:STATUS]":       skill_get_file_status,
        "[ACTION:LOGS_DAY]":     lambda: skill_get_log_history("day"),
        "[ACTION:LOGS_WEEK]":    lambda: skill_get_log_history("week"),
        "[ACTION:LOGS_MONTH]":   lambda: skill_get_log_history("month"),
        "[ACTION:LOGS_YEAR]":    lambda: skill_get_log_history("year"),
    }
    for tag, fn in action_map.items():
        if tag in reply:
            action_result = fn()
            reply = reply.replace(tag, "").strip()
            reply = f"{reply}\n\n{action_result}".strip() if reply else action_result

    return reply if reply else "(No response from Watson Assistant)"


# ─────────────────────────────────────────────────────────────────────────────
# watsonx Orchestrate chat integration
# ─────────────────────────────────────────────────────────────────────────────
def orchestrate_chat(history: list[dict], user_message: str) -> str:
    """
    Send a conversation turn to IBM watsonx Orchestrate and return the reply.

    Uses the Orchestrate SaaS REST API:
      POST https://api.{region}.watson-orchestrate.cloud.ibm.com/v1/agent_chat

    The agent must be DEPLOYED (not just saved in the builder) for this to work.

    Credentials in config.json → orchestrate:
      api_key      — IBM Cloud IAM API key
      instance_url — Orchestrate instance URL (used to extract region)
      agent_id     — Agent UUID
    """
    cfg = load_config()
    oc  = cfg.get("orchestrate", {})

    api_key      = oc.get("api_key", "")
    agent_id     = oc.get("agent_id", "")
    instance_url = oc.get("instance_url", "").rstrip("/")

    if not api_key or api_key == "YOUR_ORCHESTRATE_API_KEY":
        raise ValueError(
            "watsonx Orchestrate API key is not configured.\n"
            "Edit config.json → orchestrate.api_key and agent_id."
        )
    if not agent_id or agent_id == "YOUR_ORCHESTRATE_AGENT_ID":
        raise ValueError("Orchestrate agent_id is not set in config.json.")

    import urllib.request
    import urllib.error

    # ── Step 1: Exchange IBM Cloud API key for IAM Bearer token ──────────────
    token_req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token",
        data=f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(token_req, timeout=15) as resp:
        iam_token = json.loads(resp.read())["access_token"]

    # ── Step 2: Detect region from instance_url ───────────────────────────────
    if   "us-south" in instance_url: region = "us-south"
    elif "jp-tok"   in instance_url: region = "jp-tok"
    elif "au-syd"   in instance_url: region = "au-syd"
    else:                             region = "eu-de"

    # ── Step 3: Build conversation payload ───────────────────────────────────
    messages = []
    for turn in (history[-10:] if history else []):
        messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    payload = json.dumps({
        "agent_id": agent_id,
        "messages": messages,
    }).encode()

    # ── Step 4: POST to the SaaS API hostname (api.{region}…) ────────────────
    chat_url = f"https://api.{region}.watson-orchestrate.cloud.ibm.com/v1/agent_chat"
    chat_req = urllib.request.Request(
        chat_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {iam_token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(chat_req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        # Parse IBM error code for a friendly message
        try:
            err_json = json.loads(error_body)
            ibm_code = err_json.get("code", "")
            ibm_msg  = err_json.get("message", error_body[:300])
        except Exception:
            ibm_code = ""
            ibm_msg  = error_body[:300]

        if e.code == 500 and "WXO-PROXY-11112E" in (ibm_code + error_body):
            raise RuntimeError(
                "The Orchestrate agent is not deployed yet.\n\n"
                "To fix this:\n"
                "1. Open your Orchestrate instance\n"
                "2. Go to your Agent → click 'Deploy' or 'Publish'\n"
                "3. Once deployed, try again here."
            )
        raise RuntimeError(f"Orchestrate API error {e.code}: {ibm_msg}")

    # ── Step 5: Extract reply — handle both response shapes ───────────────────
    # Shape A: {"output": {"text": "..."}}
    # Shape B: {"choices": [{"message": {"content": "..."}}]}
    # Shape C: {"response": "..."}
    reply = ""
    if "output" in result:
        out = result["output"]
        if isinstance(out, dict):
            reply = out.get("text", "") or "\n".join(
                g.get("text","") for g in out.get("generic",[])
                if g.get("response_type") == "text"
            )
        elif isinstance(out, str):
            reply = out
    elif "choices" in result:
        reply = result["choices"][0].get("message", {}).get("content", "")
    elif "response" in result:
        reply = result["response"]
    elif "message" in result:
        reply = result["message"]

    reply = reply.strip() if reply else ""

    # ── Step 6: Handle [ACTION:*] tags the agent may return ───────────────────
    action_map = {
        "[ACTION:SCAN]":         skill_scan_box_folder,
        "[ACTION:EXTRACT_CHAT]": skill_run_extraction,
        "[ACTION:STATUS]":       skill_get_file_status,
        "[ACTION:LOGS_DAY]":     lambda: skill_get_log_history("day"),
        "[ACTION:LOGS_WEEK]":    lambda: skill_get_log_history("week"),
        "[ACTION:LOGS_MONTH]":   lambda: skill_get_log_history("month"),
        "[ACTION:LOGS_YEAR]":    lambda: skill_get_log_history("year"),
    }
    for tag, fn in action_map.items():
        if tag in reply:
            action_result = fn()
            reply = reply.replace(tag, "").strip()
            reply = f"{reply}\n\n{action_result}".strip() if reply else action_result

    return reply if reply else "(No response from Orchestrate agent)"


# ─────────────────────────────────────────────────────────────────────────────
# Flask routes — Pages
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    db        = load_tracking()
    files     = db.get("files", {})
    total     = len(files)
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    pending   = total - completed
    return render_template("home.html", total=total, completed=completed, pending=pending)


@app.route("/check")
def check():
    db    = load_tracking()
    files = db.get("files", {})
    rows  = [
        {
            "id":             fid,
            "name":           info.get("name", ""),
            "status":         info.get("status", "Pending"),
            "last_extracted": info.get("last_extracted") or "--",
            "ref_number":     info.get("ref_number") or "--",
        }
        for fid, info in files.items()
    ]
    total     = len(rows)
    completed = sum(1 for r in rows if r["status"] == "Completed")
    pending   = total - completed
    pending_rows = [r for r in rows if r["status"] == "Pending"]
    return render_template("check.html", rows=pending_rows,
                           total=total, completed=completed, pending=pending)


@app.route("/insights")
def insights():
    return render_template("insights.html")


@app.route("/extract")
def extract():
    return render_template("extract.html")


@app.route("/chat")
def chat():
    return render_template("chat.html")


# ─────────────────────────────────────────────────────────────────────────────
# Flask routes — API endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/scan", methods=["POST"])
def api_scan():
    result = skill_scan_box_folder()
    # Reload table data after scan
    db        = load_tracking()
    files     = db.get("files", {})
    total     = len(files)
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    pending   = total - completed
    return jsonify({"message": result, "total": total, "completed": completed, "pending": pending})


@app.route("/api/extract", methods=["POST"])
def api_extract():
    global _extract_running
    if _extract_running:
        return jsonify({"message": "Extraction already running. Please wait."}), 409
    thread = threading.Thread(target=skill_run_extraction, daemon=True)
    thread.start()
    return jsonify({"message": "Extraction started. Check back shortly for results."})


@app.route("/api/extract/status", methods=["GET"])
def api_extract_status():
    global _extract_running, _extract_result
    return jsonify({"running": _extract_running, "result": _extract_result})


@app.route("/api/status", methods=["GET"])
def api_status():
    db        = load_tracking()
    files     = db.get("files", {})
    total     = len(files)
    completed = sum(1 for f in files.values() if f.get("status") == "Completed")
    pending   = total - completed
    rows      = [
        {
            "id":             fid,
            "name":           info.get("name", ""),
            "status":         info.get("status", "Pending"),
            "last_extracted": info.get("last_extracted") or "--",
            "ref_number":     info.get("ref_number") or "--",
        }
        for fid, info in files.items()
        if info.get("status") == "Pending"
    ]
    return jsonify({"total": total, "completed": completed, "pending": pending, "rows": rows})


@app.route("/api/insights", methods=["GET"])
def api_insights():
    period = request.args.get("period", "Month")
    db     = load_tracking()
    files  = db.get("files", {})
    now    = datetime.now()
    buckets: dict = defaultdict(lambda: {"Pending": 0, "Completed": 0})

    for info in files.values():
        status = info.get("status", "Pending")
        ts     = info.get("last_extracted")
        dt = now
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
            except ValueError:
                dt = now

        if period == "Day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "Week":
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        elif period == "Month":
            key = dt.strftime("%b %Y")
        else:
            key = str(dt.year)

        buckets[key][status] += 1

    sorted_buckets = dict(sorted(buckets.items()))
    labels     = list(sorted_buckets.keys())
    completed  = [sorted_buckets[k]["Completed"] for k in labels]
    pending    = [sorted_buckets[k]["Pending"]   for k in labels]
    total      = len(files)
    total_comp = sum(1 for f in files.values() if f.get("status") == "Completed")
    total_pend = total - total_comp

    return jsonify({
        "labels": labels, "completed": completed, "pending": pending,
        "total": total, "total_completed": total_comp, "total_pending": total_pend,
    })


@app.route("/api/box/test", methods=["GET"])
def api_box_test():
    """
    Diagnostic endpoint — tests every step of the Box connection.
    Visit http://localhost:5000/api/box/test in your browser to see results.
    """
    steps = []

    def ok(msg):  steps.append({"status": "✅", "msg": msg})
    def fail(msg): steps.append({"status": "❌", "msg": msg})
    def info(msg): steps.append({"status": "ℹ️", "msg": msg})

    # ── Step 1: Config ────────────────────────────────────────────────────────
    try:
        cfg     = load_config()
        box_cfg = cfg.get("box", {})
        output_folder_id = box_cfg.get("output_folder_id", "")
        source_folder_id = box_cfg.get("folder_id", "")
        jwt_filename     = box_cfg.get("jwt_config_file", "box_jwt_config.json")
        info(f"Config loaded — output_folder_id: {output_folder_id or '(not set)'}")
        if not output_folder_id:
            fail("output_folder_id is not set in config.json → box")
    except Exception as e:
        fail(f"Config load failed: {e}")
        return jsonify({"steps": steps})

    # ── Step 2: JWT file ──────────────────────────────────────────────────────
    candidates = [BASE_DIR / jwt_filename, BASE_DIR.parent / "PDF Extractor" / jwt_filename]
    jwt_path = next((p.resolve() for p in candidates if p.exists()), None)
    if jwt_path:
        ok(f"JWT config found: {jwt_path}")
    else:
        fail(f"JWT config '{jwt_filename}' not found in: {[str(p) for p in candidates]}")
        return jsonify({"steps": steps})

    # ── Step 3: Box auth ──────────────────────────────────────────────────────
    try:
        from boxsdk import JWTAuth, Client as BoxClient
        auth   = JWTAuth.from_settings_file(str(jwt_path))
        client = BoxClient(auth)
        me     = client.user().get()
        ok(f"Box auth OK — service account: {me.name} (id={me.id})")
    except Exception as e:
        fail(f"Box auth failed: {e}")
        return jsonify({"steps": steps})

    # ── Step 4: Source folder access ──────────────────────────────────────────
    try:
        items = list(client.folder(source_folder_id).get_items(limit=10))
        ok(f"Source folder {source_folder_id} accessible — {len(items)} item(s) visible")
    except Exception as e:
        fail(f"Source folder {source_folder_id} not accessible: {e}")

    # ── Step 5: Output folder access ─────────────────────────────────────────
    try:
        items = list(client.folder(output_folder_id).get_items(limit=10))
        ok(f"Output folder {output_folder_id} accessible — {len(items)} item(s) visible")
    except Exception as e:
        fail(f"Output folder {output_folder_id} not accessible: {e}")
        return jsonify({"steps": steps})

    # ── Step 6: Create test subfolder ─────────────────────────────────────────
    test_folder_id = None
    try:
        test_folder_id = _box_get_or_create_subfolder(client, output_folder_id, "_connection_test")
        ok(f"Subfolder create/find OK — id: {test_folder_id}")
    except Exception as e:
        fail(f"Subfolder create failed in output folder: {e}")
        return jsonify({"steps": steps})

    # ── Step 7: Upload a tiny test file ──────────────────────────────────────
    try:
        import io
        test_bytes = b'{"test": "box_connection_ok"}'
        box_file   = client.folder(test_folder_id).upload_stream(
            io.BytesIO(test_bytes), "_test_upload.json"
        )
        ok(f"Test file uploaded OK — Box file id: {box_file.id}")
        # Clean up test file
        client.file(box_file.id).delete()
        ok("Test file deleted (cleanup OK)")
    except Exception as e:
        fail(f"Test file upload failed: {e}")

    # ── Step 8: Clean up test folder ─────────────────────────────────────────
    try:
        client.folder(test_folder_id).delete()
        ok("Test subfolder deleted (cleanup OK)")
    except Exception as e:
        info(f"Test subfolder cleanup skipped: {e}")

    passed = sum(1 for s in steps if s["status"] == "✅")
    failed = sum(1 for s in steps if s["status"] == "❌")
    summary = f"{passed} passed, {failed} failed"

    html = f"""<!DOCTYPE html><html><head><title>Box Connection Test</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 760px; margin: 40px auto; padding: 0 20px; color: #1f2328; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .summary {{ font-size: 13px; color: #57606a; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  td:first-child {{ width: 32px; text-align: center; }}
  tr:last-child td {{ border-bottom: none; }}
  .ok  {{ background: #f0fdf4; }}
  .err {{ background: #fff5f5; }}
  .inf {{ background: #f7f8fa; }}
</style></head><body>
<h1>📦 Box Connection Test</h1>
<p class="summary">{summary} — output folder ID: <code>{output_folder_id}</code></p>
<table>"""

    for s in steps:
        cls = "ok" if s["status"] == "✅" else ("err" if s["status"] == "❌" else "inf")
        html += f'<tr class="{cls}"><td>{s["status"]}</td><td>{s["msg"]}</td></tr>'

    html += "</table></body></html>"
    return html, 200, {"Content-Type": "text/html"}


@app.route("/api/download/<path:rel_path>")
def api_download(rel_path: str):
    """Serve a local extract file (Word/Excel/JSON) as a browser download.

    rel_path is relative to BASE_DIR, e.g.:
      Word Extracts/2026/Jul_2026_Extracts/Week_28/2026-07-11/RN-123456_789_10/RN-123456_789_10_v3.docx
    Security: only files inside BASE_DIR are served; path traversal is blocked.
    """
    import urllib.parse
    # Decode any percent-encoding in the path segments
    decoded = urllib.parse.unquote(rel_path)
    target  = (BASE_DIR / decoded).resolve()
    # Prevent directory traversal outside BASE_DIR
    try:
        target.relative_to(BASE_DIR)
    except ValueError:
        return jsonify({"error": "Access denied"}), 403

    if not target.exists() or not target.is_file():
        return jsonify({"error": f"File not found: {decoded}"}), 404

    # Only allow our known extract extensions
    if target.suffix.lower() not in (".docx", ".xlsx", ".json", ".pdf"):
        return jsonify({"error": "File type not allowed"}), 403

    return send_file(str(target), as_attachment=True, download_name=target.name)


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination guard — applied to every LLM reply before it reaches the user
# ─────────────────────────────────────────────────────────────────────────────
_HALLUCINATION_PATTERNS = [
    # LLM role-playing a search / lookup process (with or without trailing dots)
    r"looking\s+up\s+['\"]?.+['\"]?[\s\.]*\.\.",
    r"looking\s+up\s+['\"][\w\s]+['\"]",
    r"found\s+\d+\s+match",
    r"searching\s+for\s+.+\.{2,}",
    r"i\s+found\s+(a\s+)?match",
    # LLM producing a fake report summary block (Name:/Report Type:/Date: lines)
    r"^name\s*:\s+[A-Z][a-z]",
    r"report\s+type\s*:\s+\w",
    r"date\s*:\s+\d{4}-\d{2}-\d{2}",
    # LLM producing a fake confidential report header
    r"confidential\s+background\s+check\s+report",
    r"detailed\s+report\s*:",
    # LLM inventing employment / education / identity sections
    r"employment\s+history\s*:",
    r"education\s*:\s*\n",
    r"identity\s+verification\s*:",
    r"bachelor.{0,15}degree",
    r"abc\s+corporation",  # well-known placeholder company from training data
    r"def\s+company",      # well-known placeholder from training data
    # LLM inventing a "would you like to view" offer (it's not its job)
    r"would\s+you\s+like\s+to\s+(view|see)\s+the\s+full\s+report",
    # LLM producing "Criminal Records: No criminal records found" style lines
    r"criminal\s+records?\s*:\s*no\s+criminal",
    r"no\s+felony\s+or\s+misdemeanor",
    # LLM producing "Government-issued ID verified" style lines
    r"government.{0,10}issued\s+id\s+verified",
    # LLM leaking internal §MARKER§ formatting protocol
    r"\u00a7[A-Z_]+\u00a7",
]
_HALLUCINATION_RE = re.compile("|".join(_HALLUCINATION_PATTERNS), re.IGNORECASE | re.MULTILINE)

# Regex that strips any stray §MARKER§ fragments from an LLM reply before
# returning it — belt-and-suspenders in case the hallucination guard fires late.
_MARKER_STRIP_RE = re.compile(r"\u00a7[A-Z_§]+\u00a7?", re.IGNORECASE)


def _is_hallucinated_reply(reply: str) -> bool:
    """Return True if the LLM reply contains fabricated report patterns."""
    return bool(_HALLUCINATION_RE.search(reply))


def _sanitize_history(history: list[dict]) -> list[dict]:
    """Strip assistant turns that contain hallucinated report data from the
    history before sending it to the LLM, so it cannot build on prior
    fabrications.  User turns are always kept."""
    clean = []
    for turn in history:
        if turn.get("role") == "assistant" and _is_hallucinated_reply(turn.get("content", "")):
            # Replace the fabricated assistant turn with a neutral placeholder
            # so the conversation flow is not broken but the bad data is gone.
            clean.append({
                "role": "assistant",
                "content": (
                    "I can only answer from our extracted records. "
                    "Please use 'look up [name or reference]' to retrieve the report first."
                ),
            })
        else:
            clean.append(turn)
    return clean


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data    = request.get_json(force=True)
    message = data.get("message", "").strip()
    history = _sanitize_history(data.get("history", []))

    if not message:
        return jsonify({"reply": "Please enter a message."}), 400

    lower = message.lower()

    # ── Local skill commands — evaluated BEFORE any lookup or LLM call ────────
    # These are hard-matched first so single-word commands like "scan" or
    # "extract" can never leak through to the LLM and trigger hallucinations.

    # Scan
    if any(kw in lower for kw in (
        "scan box", "scan folder", "check box", "scan", "rescan",
    )):
        return jsonify({"reply": skill_scan_box_folder(), "action": "scan"})

    # Extraction
    if any(kw in lower for kw in (
        "run extract", "start extract", "extract now", "extract files",
        "run pipeline", "extract", "process files", "process reports",
    )):
        thread = threading.Thread(target=skill_run_extraction, daemon=True)
        thread.start()
        return jsonify({"reply": "Extraction started. I'll have results shortly.", "action": "extract"})

    # File status — must be about files/counts, never about a person's overall status
    if any(kw in lower for kw in (
        "file status", "how many files", "pending files", "files pending",
        "files completed", "file count",
    )):
        return jsonify({"reply": skill_get_file_status()})

    # Logs — checked BEFORE lookup patterns so "show logs" doesn't hit the
    # "show me" lookup regex
    if any(kw in lower for kw in (
        "show logs", "view logs", "logs today", "logs this week",
        "logs this month", "logs this year", "extraction log",
        "extraction history", "show log", "view log", "logs",
    )):
        period = "year" if "year" in lower else "month" if "month" in lower else "week" if "week" in lower else "day"
        return jsonify({"reply": skill_get_log_history(period)})

    # ── Conversation-context follow-up ───────────────────────────────────────
    # If the bot's last message was asking for a name/ref (pending clarification
    # for a "generate reports" request), treat the user's reply as the query for
    # that pending action — even if it looks like a bare name.
    _PENDING_DOWNLOAD_MARKERS = (
        "which report would you like to download",
        "please specify a name",
        "tell me the month/week/year",
        "no report files found for",   # user is retrying after a not-found response
        "if the report hasn't been extracted",
    )
    _last_assistant = next(
        (t.get("content", "") for t in reversed(history) if t.get("role") == "assistant"),
        ""
    )
    if any(m in _last_assistant.lower() for m in _PENDING_DOWNLOAD_MARKERS):
        # User is answering the "which report?" question — run generate, not lookup
        return jsonify({"reply": skill_generate_reports(message.strip())})

    # ── Report download / generate ────────────────────────────────────────────
    # Triggered by: "generate reports", "reports for X", "download reports",
    # "get reports for X", "generate me reports for X"
    _REPORT_PATTERNS = [
        r"generate\s+(?:me\s+)?reports?\s+(?:for\s+)?(.+)",
        r"download\s+reports?\s+(?:for\s+)?(.+)",
        r"get\s+reports?\s+(?:for\s+)?(.+)",
        r"reports?\s+for\s+(.+)",
        r"export\s+reports?\s+(?:for\s+)?(.+)",
    ]
    for _rp in _REPORT_PATTERNS:
        _rm = re.match(_rp, lower.strip(), re.IGNORECASE)
        if _rm:
            _rq = _rm.group(1).strip()
            _rq = re.sub(r"\s*(?:please|now|thanks?)\s*$", "", _rq, flags=re.IGNORECASE).strip()
            return jsonify({"reply": skill_generate_reports(_rq)})
    # Bare "generate reports" / "reports" / "download reports" with no name
    if re.match(r"^(generate\s+(?:me\s+)?reports?|download\s+reports?|get\s+reports?|reports?)$",
                lower.strip(), re.IGNORECASE):
        return jsonify({"reply": skill_generate_reports("")})

    # ── Report lookup — verb-prefixed patterns ────────────────────────────────
    _LOOKUP_PATTERNS = [
        r"(?:look\s*up|lookup)\s+(.+)",
        r"show\s+me\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"find\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"get\s+(?:the\s+)?report\s+(?:for|of|on)\s+(.+)",
        r"tell\s+me\s+about\s+(.+)",
        r"(?:report\s+(?:for|of|on)|details?\s+(?:for|of|on)|info(?:rmation)?\s+(?:for|of|on|about))\s+(.+)",
        r"(?:display|pull\s+up)\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"search\s+for\s+(.+)",
        # "overall status Manalo" / "status for Manalo" / "status of RN-123"
        r"(?:overall\s+status|status)\s+(?:(?:for|of|on)\s+)?(.+)",
        # "Social Media Screening for Manalo" / "Adverse Media Check for Reyes"
        # MUST include a name after "for/of/on" — bare check-name alone does NOT match
        r"(?:adverse\s+media|global\s+sanctions|bankruptcy|financial|credit|directorship|"
        r"civil\s+litigation|professional\s+licen[sc]e|social\s+media)\s+"
        r"(?:check|screening|verification)?\s*(?:for|of|on)\s+(.+)",
    ]
    # Detect if the message is a check-specific query so we can highlight that section
    _CHECK_SECTION_RE = re.compile(
        r"^(adverse\s+media|global\s+sanctions|bankruptcy|financial(?:/credit)?|"
        r"credit|directorship|civil\s+litigation|professional\s+licen[sc]e|social\s+media)"
        r"\s*(?:check|screening|verification)?",
        re.IGNORECASE,
    )
    _check_section_match = _CHECK_SECTION_RE.match(lower.strip())
    _highlight_section   = _check_section_match.group(1).strip().title() if _check_section_match else None

    for _pat in _LOOKUP_PATTERNS:
        _m = re.match(_pat, lower.strip(), re.IGNORECASE)
        if _m:
            query = _m.group(1).strip()
            query = re.sub(r"\s*(?:please|now|thanks?|report|record|details?)\s*$", "", query, flags=re.IGNORECASE).strip()
            if query and len(query) >= 3:
                result = skill_lookup_report(query)
                if not result.startswith("No reports found"):
                    resp = {"reply": result}
                    if _highlight_section:
                        resp["highlight"] = _highlight_section
                    return jsonify(resp)
                # A lookup verb was used — the intent is clearly a record search.
                # Return "not found" directly; never let the LLM fabricate a result.
                return jsonify({"reply": (
                    f"No records found matching **'{query}'** in our extracted reports.\n"
                    "Please check the name or reference number and try again, "
                    "or run an extraction if the report has not been processed yet."
                )})
    # ── Bare check-name without a person (e.g. "Social Media Screening") ─────
    # The user is asking about a specific check section — redirect to lookup.
    _CHECK_NAME_RE = re.compile(
        r"^(?:adverse\s+media|global\s+sanctions|bankruptcy|financial(?:/credit)?|"
        r"credit|directorship|civil\s+litigation|professional\s+licen[sc]e|"
        r"social\s+media)\s*(?:check|screening|verification)?$",
        re.IGNORECASE,
    )
    if _CHECK_NAME_RE.match(lower.strip()):
        return jsonify({"reply": (
            "Which person's **" + message.strip() + "** result would you like to see?\n"
            "Please use: **'look up [name]'** or **'" + message.strip() + " for [name]'**"
        )})

    # ── Bare name / reference typed directly — try grounded lookup first ──────
    # Strip any leading status/info prefix words before searching, so that
    # "overall status Manalo" → searches for "Manalo", not the full phrase.
    _PREFIX_STRIP = re.compile(
        r"^(?:overall\s+status|status|report|details?|info(?:rmation)?)\s+(?:(?:for|of|on|about)\s+)?",
        re.IGNORECASE,
    )
    # Words/phrases that are NEVER subject names — if the bare text (after
    # prefix-stripping) matches any of these, skip the lookup entirely.
    _reserved = {
        # single-word commands
        "scan", "rescan", "extract", "status", "logs", "log", "help",
        "hello", "hi", "hey", "yes", "no", "ok", "okay", "sure",
        "thanks", "thank", "clear", "quit", "exit",
        # UI / navigation phrases
        "insights", "dashboard", "home", "check", "check box",
        "file insights", "show file insights", "show insights",
        "view insights", "show dashboard", "view dashboard",
        "show status", "show file status", "view file status",
        "overall status", "what is the overall status",
        "pipeline", "run pipeline", "process",
    }
    _bare = _PREFIX_STRIP.sub("", message.strip()).strip()
    _bare_lower = _bare.lower()
    if (
        len(_bare) >= 3
        and len(_bare) <= 60                        # names are short
        and _bare_lower not in _reserved            # check stripped version
        and lower.strip() not in _reserved          # check original too
        and re.search(r"[a-zA-Z]", _bare)           # must contain a letter
        and len(_bare.split()) <= 5                 # 5 words max — names, not sentences
        and not re.search(r"\s{2,}", _bare)         # no double spaces
    ):
        _bare_result = skill_lookup_report(_bare)
        if not _bare_result.startswith("No reports found"):
            return jsonify({"reply": _bare_result})
        # The message looks like a name/ref and no record was found.
        # Return "not found" directly — never let the LLM fabricate.
        return jsonify({"reply": (
            f"No records found matching **'{_bare}'** in our extracted reports.\n"
            "Please check the name or reference number and try again, "
            "or run an extraction if the report has not been processed yet."
        )})

    # ── Affirmative follow-up after a lookup result already in history ────────
    # Re-runs the grounded lookup so the LLM never fabricates the follow-up.
    _affirmative = {"yes", "yeah", "yep", "sure", "show", "view", "show me", "show details",
                    "view details", "full report", "full details", "show report", "view report",
                    "show full", "view full", "more details", "more info", "see more",
                    "overall status", "what is the overall status", "status"}
    if lower.strip() in _affirmative or lower.strip().startswith(("yes ", "show ", "view ", "overall status")):
        for turn in reversed(history):
            if turn.get("role") == "assistant":
                prev = turn.get("content", "")
                subj_match = re.search(r"Subject:\s*([^\|]+)", prev)
                if subj_match:
                    subject_name = subj_match.group(1).strip()
                    return jsonify({"reply": skill_lookup_report(subject_name)})
                break

    cfg = load_config()

    # Build grounded context anchor once — reused by whichever LLM is called
    grounded_context = None
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            prev = turn.get("content", "")
            if re.search(r"Subject:\s*[^\|]+\|", prev):
                grounded_context = prev
                break

    # ── Absolute pre-LLM guard ────────────────────────────────────────────────
    # If no grounded record has been established in this conversation yet,
    # the LLM has ZERO data to work from.  Any question that could prompt it
    # to fabricate person/report data must be blocked here — before the LLM
    # is ever called — so hallucinations are structurally impossible.
    #
    # Patterns that signal "the user wants report data" but we have no anchor:
    _REPORT_INQUIRY_RE = re.compile(
        r"(?:yes|yeah|yep|sure|show|view|full\s+report|full\s+details?|"
        r"more\s+(?:details?|info)|see\s+more|tell\s+me\s+more|"
        r"what\s+(?:is|are|was|were)|who\s+is|background\s+check|"
        r"criminal\s+record|employment\s+(?:history|verification)|"
        r"identity\s+verif|education|reference\s+check|"
        r"report\s+(?:for|of|on|details?)|check\s+result)",
        re.IGNORECASE,
    )
    if not grounded_context and _REPORT_INQUIRY_RE.search(lower):
        return jsonify({"reply": (
            "I don't have any extracted records loaded in this conversation yet.\n\n"
            "Please use **'look up [name or reference]'** to retrieve a report first, "
            "then ask your question — I'll answer only from that data."
        )})

    def _build_anchored_history(hist):
        """Prepend extracted record as a system anchor so the LLM cannot fabricate."""
        if not grounded_context:
            return hist
        return [
            {
                "role": "system",
                "content": (
                    "The following is the ONLY data you are permitted to use when "
                    "answering questions about this person. Do not add, infer, or "
                    "invent anything beyond what is listed here.\n\n"
                    "EXTRACTED RECORD:\n" + grounded_context
                ),
            }
        ] + hist

    # Shared hard-stop reply used when a post-LLM hallucination is detected
    _HALLUCINATION_BLOCKED = (
        "I can only answer from our extracted records. "
        "Please use **'look up [name or reference]'** to retrieve the report first, "
        "then ask your question."
    )

    # ── Priority 1: IBM Granite via watsonx.ai (if configured) ───────────────
    granite_ready = (
        cfg.get("watsonx", {}).get("api_key", "") not in ("", "YOUR_WATSONX_API_KEY")
        and cfg.get("watsonx", {}).get("project_id", "") not in ("", "YOUR_WATSONX_PROJECT_ID")
    )
    if granite_ready:
        try:
            reply = _MARKER_STRIP_RE.sub("", granite_chat(_build_anchored_history(history), message))
            if _is_hallucinated_reply(reply):
                return jsonify({"reply": _HALLUCINATION_BLOCKED, "model": "granite"})
            return jsonify({"reply": reply, "model": "granite"})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            # Fall through to ICA on error
            pass

    # ── Priority 2: IBM Consulting Advantage ICA 1.0 (if configured) ─────────
    ica_ready = (
        cfg.get("ica", {}).get("full_cookie", "") != ""
        and cfg.get("ica", {}).get("team_id", "") != ""
        and cfg.get("ica", {}).get("chat_id", "") != ""
    )
    if ica_ready:
        try:
            reply = _MARKER_STRIP_RE.sub("", ica_chat(_build_anchored_history(history), message))
            if _is_hallucinated_reply(reply):
                return jsonify({"reply": _HALLUCINATION_BLOCKED, "model": "ica"})
            return jsonify({"reply": reply, "model": "ica"})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return jsonify({"reply": f"⚠ ICA error: {exc}\n\nPlease check the server console for details."})

    # ── Priority 4: watsonx Orchestrate (if configured) ──────────────────────
    orchestrate_ready = (
        cfg.get("orchestrate", {}).get("api_key", "") not in ("", "YOUR_ORCHESTRATE_API_KEY")
        and cfg.get("orchestrate", {}).get("agent_id", "") not in ("", "YOUR_ORCHESTRATE_AGENT_ID")
    )
    if orchestrate_ready:
        try:
            reply = orchestrate_chat(history, message)
            return jsonify({"reply": reply})
        except Exception:
            pass  # fall through

    # ── Priority 5: Watson Assistant (if configured) ──────────────────────────
    wa_ready = (
        cfg.get("watson_assistant", {}).get("api_key", "") not in ("", "YOUR_WATSON_ASSISTANT_API_KEY")
        and cfg.get("watson_assistant", {}).get("assistant_id", "") not in ("", "YOUR_WATSON_ASSISTANT_ASSISTANT_ID")
        and cfg.get("watson_assistant", {}).get("service_url", "") not in ("", "YOUR_WATSON_ASSISTANT_SERVICE_URL")
    )
    if wa_ready:
        try:
            reply = watson_assistant_chat(history, message)
            return jsonify({"reply": reply})
        except Exception:
            pass  # fall through

    # ── Local fallback ────────────────────────────────────────────────────────
    return jsonify({"reply": (
        "Hi! I'm **Detective Conan**. I can help with:\n"
        "• **\"scan box\"** — scan Box folder for new PDFs\n"
        "• **\"run extraction\"** — process pending reports\n"
        "• **\"file status\"** — show counts\n"
        "• **\"look up [name]\"** — search reports\n"
        "• **\"logs this week\"** — view history"
    )})


@app.route("/api/logs", methods=["GET"])
def api_logs():
    period = request.args.get("period", "day")
    return jsonify({"summary": skill_get_log_history(period)})


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
