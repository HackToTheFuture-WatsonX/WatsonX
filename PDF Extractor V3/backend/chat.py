"""
chat.py — AI Assistant routing for PDF Extractor V3.
Ported from route_chat_message, ica_chat, skill_lookup_report, and all helpers
(pdf_extractor_ui_v2.py lines 1862–2987).
"""
import json
import logging
import re as _re_ai
import urllib.parse as _urlparse
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from config import (
    read_config, read_config_safe, write_config,
    extracted_folder, ai_json_dir, _data_dir,
    bee_prompt_text,
)
from tracking import load_tracking
from insights import get_log_history

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Logging ───────────────────────────────────────────────────────────────────
#
# ICA requests were previously opaque: failures (especially poll errors) were
# swallowed silently, so when a test "hung" there was no way to see what the
# request was or why it wasn't responding. We now write a dedicated ICA log to
# the data dir (alongside the app's other logs) plus the console, so both the
# request shape and every failure are recoverable after the fact.
log = logging.getLogger("ica")
if not log.handlers:
    log.setLevel(logging.INFO)
    try:
        _ica_log_path = _data_dir() / "ica.log"
        _fh = logging.FileHandler(_ica_log_path, encoding="utf-8")
        _fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s"))
        log.addHandler(_fh)
    except Exception:  # noqa: BLE001 — never let logging setup break chat
        pass
    _sh = logging.StreamHandler()
    _sh.setFormatter(logging.Formatter("[ica] %(levelname)s %(message)s"))
    log.addHandler(_sh)


def _redact_cookie(cookie: str) -> str:
    """Return a safe-to-log cookie fingerprint (length + names only, no values)."""
    if not cookie:
        return "<empty>"
    names = []
    for part in cookie.split(";"):
        name = part.split("=", 1)[0].strip()
        if name:
            names.append(name)
    return f"<{len(cookie)} chars, {len(names)} cookies: {', '.join(names[:12])}>"


def _log_ica_request_context(where: str, *, cookie, team_id, team_name,
                             chat_id, base_url, url):
    """Log the full request context (with the cookie redacted) so a failing or
    non-responding request can be diagnosed from the log alone."""
    log.info("[%s] ICA request context:", where)
    log.info("[%s]   base_url  = %s", where, base_url)
    log.info("[%s]   url       = %s", where, url)
    log.info("[%s]   team_id   = %s", where, team_id or "<empty>")
    log.info("[%s]   team_name = %s", where, team_name or "<empty>")
    log.info("[%s]   chat_id   = %s", where, chat_id or "<empty>")
    log.info("[%s]   cookie    = %s", where, _redact_cookie(cookie))


# ── Status helper ─────────────────────────────────────────────────────────────
_STATUS_EMOJI = {
    "cleared": "✅", "verified": "✅", "pass": "✅", "passed": "✅", "clear": "✅",
    "failed": "❌", "fail": "❌", "unverified": "❌", "adverse": "❌",
    "--": "⬜", "": "⬜",
}

def _status_icon(val: str) -> str:
    v = (val or "").strip().lower()
    for key, icon in _STATUS_EMOJI.items():
        if key and key in v:
            return icon
    return "🔵"


def _name_matches(query_lower: str, stored_name: str) -> bool:
    stored_lower = stored_name.lower()
    if query_lower in stored_lower:
        return True
    if "," in stored_lower:
        parts        = [p.strip() for p in stored_lower.split(",", 1)]
        reversed_name = f"{parts[1]} {parts[0]}".strip()
        if query_lower in reversed_name:
            return True
        name_tokens  = set(stored_lower.replace(",", " ").split())
        query_tokens = set(query_lower.split())
        if query_tokens and query_tokens.issubset(name_tokens):
            return True
    return False


# ── Report lookup ─────────────────────────────────────────────────────────────

OTHER_CHECK_ORDER = [
    "Adverse Media Check", "Global Sanctions", "Bankruptcy Check",
    "Financial/Credit Check", "Directorship Check", "Civil Litigation Check",
    "Professional License Qualification", "Social Media Screening",
]


def skill_lookup_report(query: str) -> str:
    if not query.strip():
        return "Please provide a name or reference number to search for."

    q_lower    = query.strip().lower()
    best_by_ref: dict = {}
    json_dir   = ai_json_dir()

    def _ingest(report: dict):
        s   = report.get("report_summary", {})
        name = s.get("subject_name", "")
        ref  = s.get("case_reference", "").strip()
        key  = ref.lower() or name.lower()
        if not _name_matches(q_lower, name) and q_lower not in key:
            return
        existing = best_by_ref.get(key)
        if existing is None or (
            (report.get("extracted_at", "") or "") > (existing.get("extracted_at", "") or "")
        ):
            best_by_ref[key] = report

    if json_dir.exists():
        for jp in json_dir.rglob("*.json"):
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    _ingest(json.load(fh))
            except Exception:
                continue

    if not best_by_ref:
        return f"No reports found matching '{query}'."

    matches = sorted(
        best_by_ref.values(),
        key=lambda r: r.get("report_summary", {}).get("subject_name", "").lower(),
    )

    def _build_block(r: dict, index: int, total: int) -> str:
        s        = r.get("report_summary", {})
        subject  = s.get("subject_name", "--")
        ref_num  = s.get("case_reference", "--")
        delivery = s.get("delivery_date", "--")
        received = s.get("case_received", "")
        package  = s.get("package", "")
        overall  = s.get("overall_status", "--")
        lines = []
        if total > 1:
            lines += [f"{'─'*50}", f"Record {index} of {total}"]
        lines.append(f"Subject: {subject} | Ref: {ref_num} | Delivery: {delivery}")
        if received and received.strip():
            lines.append(f"Case Received: {received}")
        if package and package.strip():
            lines.append(f"Package: {package}")
        lines.append(f"Overall Status: {_status_icon(overall)} {overall}\n")
        for ec in r.get("employment_checks", []):
            emp_status = ec.get("verification_status", "--")
            lines.append(f"── Employment Verification ──")
            lines.append(f"  {_status_icon(emp_status)} Employment {ec.get('check_number','?')}: "
                         f"{ec.get('employer_name','--')} — {emp_status}")
            for label, key in [
                ("Position","position_title"), ("Dates","dates_of_employment"),
                ("Result","result"), ("Notes","notes"),
            ]:
                val = ec.get(key, "")
                if val and str(val).strip():
                    lines.append(f"    {label}: {val}")
            lines.append("")
        for pr in r.get("professional_reference_checks", []):
            ref_status = pr.get("verification_status", "--")
            lines.append(f"── Professional References ──")
            lines.append(f"  {_status_icon(ref_status)} Reference {pr.get('check_number','?')}: "
                         f"{pr.get('referee_name','--')} — {ref_status}")
            for qa in pr.get("qa", []):
                a = qa.get("answer","").strip(); q = qa.get("question","").strip()
                if a and q:
                    lines += [f"    Q: {q}", f"    A: {a}"]
            lines.append("")
        other_map = {oc.get("check_name","").strip().lower(): oc for oc in r.get("other_checks", [])}
        lines.append("── Database Checks ──")
        for check_name in OTHER_CHECK_ORDER:
            oc     = next((v for k, v in other_map.items() if k == check_name.lower()), {})
            status = oc.get("status", "--") if oc else "--"
            lines.append(f"  {_status_icon(status)} {check_name}: {status}")
        return "\n".join(lines)

    total  = len(matches)
    blocks = [_build_block(r, i + 1, total) for i, r in enumerate(matches)]
    header = ""
    if total > 1:
        header = (
            f"Found {total} record(s) matching '{query}':\n"
            + "\n".join(
                f"  {i+1}. {r.get('report_summary',{}).get('subject_name','--')} "
                f"— Ref: {r.get('report_summary',{}).get('case_reference','--')}"
                for i, r in enumerate(matches)
            ) + "\n\n"
        )
    return header + "\n\n".join(blocks)


def _find_report_files(query: str) -> list[dict]:
    ext_root  = extracted_folder()
    json_root = ext_root / "JSON File Extracts"
    if not json_root.exists():
        return []
    q_lower   = query.lower().strip()
    matches   = []
    seen_refs = set()
    for jpath in sorted(json_root.rglob("*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data    = json.loads(jpath.read_text(encoding="utf-8"))
            summary = data.get("report_summary", {})
            subject = summary.get("subject_name", "").strip()
            ref     = summary.get("case_reference", "").strip()
        except Exception:
            continue
        parts  = subject.lower().replace(",", " ").split()
        hit    = (q_lower in subject.lower() or q_lower in ref.lower()
                  or any(q_lower == p for p in parts)
                  or any(q_lower in p for p in parts))
        if not hit or ref in seen_refs:
            continue
        seen_refs.add(ref)
        ref_folder = jpath.parent
        ref_slug   = ref_folder.name
        word_root  = ext_root / "Word Extracts"
        excel_root = ext_root / "CSV Extracts"
        wp = next(word_root.rglob(f"{ref_slug}/*.docx"),  None) if word_root.exists() else None
        ep = next(excel_root.rglob(f"{ref_slug}/*.xlsx"), None) if excel_root.exists() else None
        matches.append({
            "subject": subject, "ref": ref,
            "json": str(jpath),
            "word": str(wp)  if wp else "",
            "excel": str(ep) if ep else "",
        })
    return matches


def _skill_list_all_reports() -> str:
    ext_root  = extracted_folder()
    json_root = ext_root / "JSON File Extracts"
    if not json_root.exists():
        return "No extracted reports found.\nRun **'extract'** first."
    seen_refs = set(); entries = []
    for jpath in sorted(json_root.rglob("*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data    = json.loads(jpath.read_text(encoding="utf-8"))
            summary = data.get("report_summary", {})
            subject = summary.get("subject_name", "").strip()
            ref     = summary.get("case_reference", "").strip()
        except Exception:
            continue
        if ref not in seen_refs:
            seen_refs.add(ref)
            entries.append(f"  • **{subject}**  (Ref: {ref})")
    if not entries:
        return "No extracted reports found.\nRun **'extract'** first."
    return (
        f"**{len(entries)}** extracted report(s) available:\n\n"
        + "\n".join(entries)
        + "\n\nTo open a file, say: **generate report for [name]**"
    )


def _skill_open_report(subject_query: str, file_type: str) -> str:
    import os as _os
    matches = _find_report_files(subject_query)
    if not matches:
        return f"No extracted reports found matching **'{subject_query}'**."
    m        = matches[0]
    path_str = m.get(file_type, "")
    if not path_str:
        return f"The **{file_type.capitalize()}** file for **{m['subject']}** was not found."
    p = Path(path_str)
    if not p.exists():
        return f"File not found on disk: `{p.name}`"
    try:
        _os.startfile(str(p))
    except Exception as exc:
        return f"⚠ Could not open file: {exc}"
    return f"✅ Opening **{p.name}** for **{m['subject']}** (Ref: {m['ref']})."


# ── ICA transport helpers ─────────────────────────────────────────────────────
#
# CRITICAL: Posting a PROMPT entry alone does NOT trigger model inference — the
# chat just accumulates PROMPT entries and no ANSWER ever appears (which is why
# the old "post prompt then poll GET /entries for an ANSWER" logic always timed
# out). The real inference trigger is a SECOND POST of an (empty) ANSWER entry
# that references the prompt's _id INSIDE content.promptEntryId. That request
# returns HTTP 201 with Content-Type: text/event-stream carrying the streamed
# answer as chunks literally prefixed with "answer: ".


def _ica_headers(cookie: str, team_id: str, team_name: str, chat_id: str,
                 *, accept: str = "application/json, text/plain, */*") -> dict:
    # ICA's gateway (Akamai) rejects raw spaces in header VALUES with HTTP 501.
    # The real browser sends teamid/teamname URL-encoded, so encode them here.
    return {
        "cookie": cookie,
        "teamid": _urlparse.quote(team_id, safe=""),
        "teamname": _urlparse.quote(team_name, safe=""),
        "Content-Type": "application/json",
        "Accept": accept,
        "Origin": "https://servicesessentials.ibm.com",
        "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
    }


def _parse_ica_sse(raw_body: str) -> str:
    """Parse an ICA text/event-stream answer body into plain text.

    The stream is a series of chunks literally prefixed with "answer: ". Most
    chunks are empty; the actual content is what remains after stripping every
    "answer: " prefix. e.g. 'answer: answer: OKanswer: ' → 'OK'.
    """
    if not raw_body:
        return ""
    return raw_body.replace("answer: ", "").strip()


def _ica_send_and_stream(where: str, *, cookie, team_id, team_name, chat_id,
                         base_url, prompt: str, timeout: int = 120) -> str:
    """Post a PROMPT then trigger + read the streamed ANSWER. Returns the reply.

    Raises RuntimeError on any transport/HTTP failure.
    """
    import urllib.request, urllib.error

    entries_url = f"{base_url}/chats/{chat_id}/entries"
    _log_ica_request_context(where, cookie=cookie, team_id=team_id,
                             team_name=team_name, chat_id=chat_id,
                             base_url=base_url, url=entries_url)

    # ── Step 1: POST the PROMPT entry ──────────────────────────────────────
    prompt_payload = json.dumps({
        "chatId": chat_id, "type": "PROMPT",
        "content": {
            "prompt": prompt, "promptId": "", "promptUuid": "",
            "isIncludedInContext": True,
            "sensitiveInformation": {"hasSensitiveInformation": False},
        },
    }).encode("utf-8")
    headers = _ica_headers(cookie, team_id, team_name, chat_id)
    log.info("[%s] POST prompt (%d chars) → %s", where, len(prompt or ""), entries_url)
    req = urllib.request.Request(entries_url, data=prompt_payload,
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            echo = json.loads(resp.read().decode("utf-8"))
        prompt_id = echo.get("_id", "") if isinstance(echo, dict) else ""
        log.info("[%s] prompt accepted (HTTP %s), _id=%s", where,
                 getattr(resp, "status", "?"), prompt_id)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        log.error("[%s] prompt POST failed HTTP %s: %s", where, e.code, body)
        raise RuntimeError(f"ICA {e.code}: {body}")
    except Exception as exc:  # noqa: BLE001
        log.error("[%s] prompt POST could not reach ICA: %s", where, exc)
        raise RuntimeError(f"ICA unreachable: {exc}")

    if not prompt_id:
        raise RuntimeError("ICA did not return a prompt entry id")

    # ── Step 2: POST the ANSWER trigger and read the SSE stream ────────────
    # promptEntryId MUST live inside content — at top level ICA replies with a
    # NOTIFICATION entry titled "No prompt entry found".
    answer_payload = json.dumps({
        "chatId": chat_id, "type": "ANSWER",
        "content": {"answer": "", "promptEntryId": prompt_id},
    }).encode("utf-8")
    sse_headers = _ica_headers(cookie, team_id, team_name, chat_id,
                               accept="text/event-stream")
    log.info("[%s] POST answer trigger (promptEntryId=%s) → %s",
             where, prompt_id, entries_url)
    ans_req = urllib.request.Request(entries_url, data=answer_payload,
                                     headers=sse_headers, method="POST")
    try:
        with urllib.request.urlopen(ans_req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        log.info("[%s] answer stream received (HTTP %s, %d bytes)", where,
                 getattr(resp, "status", "?"), len(raw))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        log.error("[%s] answer POST failed HTTP %s: %s", where, e.code, body)
        raise RuntimeError(f"ICA {e.code}: {body}")
    except Exception as exc:  # noqa: BLE001
        log.error("[%s] answer POST could not reach ICA: %s", where, exc)
        raise RuntimeError(f"ICA unreachable: {exc}")

    reply = _parse_ica_sse(raw)
    log.info("[%s] parsed reply (%d chars)", where, len(reply))
    return reply


# ── ICA chat ──────────────────────────────────────────────────────────────────


_HALLUCINATION_PATTERNS = [
    r"looking\s+up\s+['\"]?.+['\"]?[\s\.]*\.\.",
    r"found\s+\d+\s+match", r"searching\s+for\s+.+\.{2,}",
    r"i\s+found\s+(a\s+)?match", r"^name\s*:\s+[A-Z][a-z]",
    r"confidential\s+background\s+check\s+report",
    r"employment\s+history\s*:", r"identity\s+verification\s*:",
    r"government.{0,10}issued\s+id\s+verified",
    r"\u00a7[A-Z_]+\u00a7",
]
_HALLUCINATION_RE = _re_ai.compile(
    "|".join(_HALLUCINATION_PATTERNS), _re_ai.IGNORECASE | _re_ai.MULTILINE
)

def _is_hallucinated_reply(reply: str) -> bool:
    return bool(_HALLUCINATION_RE.search(reply))

def _sanitize_history(history: list[dict]) -> list[dict]:
    clean = []
    for turn in history:
        if turn.get("role") == "assistant" and _is_hallucinated_reply(turn.get("content","")):
            clean.append({"role": "assistant", "content":
                "I can only answer from our extracted records. "
                "Please use 'look up [name or reference]' to retrieve the report first."})
        else:
            clean.append(turn)
    return clean


def ica_chat(history: list[dict], user_message: str) -> str:
    cfg      = read_config()
    ic       = cfg.get("ica", {})
    cookie   = (ic.get("full_cookie", "") or "").strip()
    team_id  = ic.get("team_id", "")
    team_name = ic.get("team_name", "")
    chat_id  = ic.get("chat_id", "")
    base_url = ic.get("base_url",
        "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat").rstrip("/")

    if not cookie:  raise ValueError("ICA full_cookie not configured")
    if not team_id: raise ValueError("ICA team_id not configured")
    if not chat_id: raise ValueError("ICA chat_id not configured")

    reply = _ica_send_and_stream(
        "ica_chat", cookie=cookie, team_id=team_id, team_name=team_name,
        chat_id=chat_id, base_url=base_url, prompt=user_message, timeout=120,
    )
    return reply or "(No response)"




# ── Streaming connection tests (Server-Sent Events) ───────────────────────────
#
# These generators yield human-readable "step" dicts describing exactly what the
# connection test is doing at each moment, so the Settings UI can show live
# progress instead of a blank spinner. Each yielded dict has the shape:
#     {"step": "<message>", "state": "run"|"ok"|"error"|"done", ...}
# The final event uses state "done" (success) or "error" (failure) and may carry
# extra fields (e.g. "detail", "error").

def test_box_stream():
    """Yield step-by-step progress while testing the Box JWT connection."""
    yield {"step": "Reading configuration…", "state": "run"}
    try:
        from box_client import get_box_client
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Could not load Box client module.", "state": "error",
               "error": str(exc)[:300]}
        return

    yield {"step": "Authenticating with Box using JWT service account…", "state": "run"}
    try:
        client, cfg = get_box_client()
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Box authentication failed.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": "Authenticated with Box ✓", "state": "ok"}

    yield {"step": "Fetching current Box user…", "state": "run"}
    try:
        user = client.user().get()
        user_login = getattr(user, "login", getattr(user, "name", "unknown"))
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Could not fetch Box user.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": f"Signed in as {user_login} ✓", "state": "ok"}

    folder_id = cfg.get("box", {}).get("folder_id", "0")
    yield {"step": f"Opening configured folder (id {folder_id})…", "state": "run"}
    try:
        folder = client.folder(folder_id).get()
        folder_name = getattr(folder, "name", folder_id)
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Could not open the configured folder.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": f'Folder "{folder_name}" reachable ✓', "state": "ok"}

    yield {"step": "Box connection is working.", "state": "done",
           "detail": f'Connected as {user_login} · folder "{folder_name}"'}


def test_ica_stream():
    """Yield step-by-step progress while testing the ICA connection.

    Sends one test prompt to IBM Consulting Advantage using the two-POST flow
    (PROMPT then ANSWER trigger) and reads the streamed reply. See
    _ica_send_and_stream for the transport details.
    """
    yield {"step": "Reading ICA configuration…", "state": "run"}

    cfg       = read_config()
    ic        = cfg.get("ica", {})
    cookie    = (ic.get("full_cookie", "") or "").strip()
    team_id   = ic.get("team_id", "")
    team_name = ic.get("team_name", "")
    chat_id   = ic.get("chat_id", "")
    base_url  = ic.get(
        "base_url",
        "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat",
    ).rstrip("/")

    missing = []
    if not cookie:  missing.append("session cookie")
    if not team_id: missing.append("team ID")
    if not chat_id: missing.append("chat ID")
    if missing:
        yield {"step": f"Missing ICA credentials: {', '.join(missing)}.",
               "state": "error",
               "error": f"ICA not configured — missing {', '.join(missing)}."}
        return
    yield {"step": "Credentials present (cookie, team ID, chat ID) ✓", "state": "ok"}

    prompt = "Hi Bee"
    request_summary = (
        f"POST {base_url}/chats/{chat_id}/entries\n"
        f"Headers: teamid={team_id or '(none)'}, "
        f"teamname={team_name or '(none)'}, "
        f"cookie={_redact_cookie(cookie)}\n"
        f'Body: type=PROMPT then ANSWER trigger, prompt="{prompt}"'
    )
    yield {"step": "Preparing request to ICA…", "state": "ok",
           "detail": request_summary}
    yield {"step": f'Sending test prompt "{prompt}" to ICA…', "state": "run"}
    try:
        reply = _ica_send_and_stream(
            "test_ica_stream", cookie=cookie, team_id=team_id,
            team_name=team_name, chat_id=chat_id, base_url=base_url,
            prompt=prompt, timeout=120,
        )
    except RuntimeError as exc:
        yield {"step": "ICA request failed.", "state": "error",
               "error": str(exc)[:300]}
        return
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Could not reach ICA.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": "Reply received from ICA ✓", "state": "ok"}
    yield {"step": "ICA connection is working.", "state": "done",
           "detail": f"Reply: {(reply or '(empty)')[:120]}"}


def initialize_ica_system_prompt():
    """Yield step-by-step progress while priming the ICA chat with bee_prompt.md.

    Sends the Bee system prompt as the first PROMPT to the currently configured
    chat_id. On success, records that chat_id in config.ica.system_prompt_chat_id
    so the UI can show "primed" and later runs can skip re-priming.
    """
    yield {"step": "Loading bee_prompt.md…", "state": "run"}
    prompt = bee_prompt_text()
    if not prompt:
        yield {"step": "Could not load bee_prompt.md.", "state": "error",
               "error": "bee_prompt.md is missing or empty. "
                        "Expected at backend/prompt/bee_prompt.md."}
        return
    yield {"step": f"Loaded bee_prompt.md ({len(prompt)} chars) ✓", "state": "ok"}

    yield {"step": "Reading ICA configuration…", "state": "run"}
    cfg       = read_config_safe()
    ic        = cfg.get("ica", {})
    cookie    = (ic.get("full_cookie", "") or "").strip()
    team_id   = ic.get("team_id", "")
    team_name = ic.get("team_name", "")
    chat_id   = ic.get("chat_id", "")
    base_url  = ic.get(
        "base_url",
        "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat",
    ).rstrip("/")

    missing = []
    if not cookie:  missing.append("session cookie")
    if not team_id: missing.append("team ID")
    if not chat_id: missing.append("chat ID")
    if missing:
        yield {"step": f"Missing ICA credentials: {', '.join(missing)}.",
               "state": "error",
               "error": f"ICA not configured — missing {', '.join(missing)}."}
        return
    yield {"step": "Credentials present (cookie, team ID, chat ID) ✓", "state": "ok"}

    request_summary = (
        f"POST {base_url}/chats/{chat_id}/entries\n"
        f"Headers: teamid={team_id or '(none)'}, "
        f"teamname={team_name or '(none)'}, "
        f"cookie={_redact_cookie(cookie)}\n"
        f"Body: type=PROMPT then ANSWER trigger, prompt=bee_prompt.md ({len(prompt)} chars)"
    )
    yield {"step": "Preparing request to ICA…", "state": "ok",
           "detail": request_summary}
    yield {"step": "Sending Bee system prompt to ICA…", "state": "run"}
    try:
        reply = _ica_send_and_stream(
            "initialize_ica_system_prompt", cookie=cookie, team_id=team_id,
            team_name=team_name, chat_id=chat_id, base_url=base_url,
            prompt=prompt, timeout=180,
        )
    except RuntimeError as exc:
        yield {"step": "ICA priming request failed.", "state": "error",
               "error": str(exc)[:300]}
        return
    except Exception as exc:  # noqa: BLE001
        yield {"step": "Could not reach ICA.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": "Bee prompt accepted by ICA ✓", "state": "ok"}

    # Record which chat_id we primed so the UI can show "primed" state and skip
    # re-priming next time. Re-read config to avoid clobbering concurrent edits.
    try:
        latest = read_config_safe()
        latest.setdefault("ica", {})["system_prompt_chat_id"] = chat_id
        write_config(latest)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not persist system_prompt_chat_id: %s", exc)
        yield {"step": "Prompt sent but could not persist state.", "state": "error",
               "error": str(exc)[:300]}
        return
    yield {"step": f"Marked chat_id {chat_id[:8]}… as primed ✓", "state": "ok"}

    yield {"step": "ICA system prompt initialized.", "state": "done",
           "detail": f"Reply: {(reply or '(empty)')[:120]}"}



# ── Route orchestrator ────────────────────────────────────────────────────────


def trigger_scan_for_chat() -> str:
    from scanner import run_scan
    try:
        s = run_scan()
        return (
            f"🔍 Scan complete — **{s['found']}** PDF(s) found.\n"
            f"**Total:** {s['total']}   |   ✅ Completed: {s['completed']}   |   🕐 Pending: {s['pending']}"
        )
    except Exception as exc:
        return f"⚠ Scan failed: {str(exc)[:200]}"


def trigger_sync_for_chat() -> str:
    from sync import sync_box_to_local
    try:
        downloaded, skipped, errors = sync_box_to_local()
        lines = [f"🔄 Sync complete — **{downloaded}** downloaded, **{skipped}** existed, "
                 f"**{len(errors)}** error(s)."]
        if errors:
            lines += [""] + [f"  ⚠ {e}" for e in errors]
        lines += ["", trigger_scan_for_chat(), "", "Ready — type **'extract'** to process new files."]
        return "\n".join(lines)
    except Exception as exc:
        return f"⚠ Sync failed: {str(exc)[:300]}"


def trigger_extraction_for_chat() -> str:
    from extractor import run_extraction
    try:
        results = run_extraction()
        completed = sum(1 for r in results if r.get("status") == "ok")
        failed    = sum(1 for r in results if r.get("status") == "error")
        header    = (
            f"Extraction complete.\n"
            f"Files: {len(results)}   |   Completed: {completed}   |   Failed: {failed}"
        )
        payload = json.dumps({"header": header, "items": results})
        return f"\u00a7LINKS\u00a7{payload}\u00a7LINKS\u00a7"
    except Exception as exc:
        return f"⚠ Extraction failed: {str(exc)[:300]}"


def _kw_match(lower: str, *keywords: str) -> bool:
    """Word-boundary match for single words; substring for multi-word phrases.

    Plain substring matching wrongly fired the extract pipeline on words like
    "extracted"/"extraction" (and similarly for "scan"/"sync" appearing inside
    other words). Single-word keywords are matched on word boundaries; multi-word
    phrases keep substring matching.
    """
    for kw in keywords:
        if " " in kw:
            if kw in lower:
                return True
        else:
            if _re_ai.search(r"\b" + _re_ai.escape(kw) + r"\b", lower):
                return True
    return False


def route_chat_message(message: str, history: list[dict]) -> str:
    history = _sanitize_history(history)
    lower   = message.lower()

    if _kw_match(lower, "sync folder","sync now","sync box","synchronise","synchronize","sync"):
        return trigger_sync_for_chat()
    if _kw_match(lower, "scan box","scan folder","check box","rescan","scan"):
        return trigger_scan_for_chat()
    if _kw_match(lower, "run extract","start extract","extract now","extract files","run pipeline","process files","process reports","extract"):
        return trigger_extraction_for_chat()
    if any(kw in lower for kw in ("file status","how many files","pending files","files pending","files completed","file count")):
        db = load_tracking(); files = db.get("files", {})
        total = len(files); completed = sum(1 for f in files.values() if f.get("status") == "Completed")
        return f"File Status:\n  Total: {total}\n  Completed: {completed}\n  Pending: {total - completed}"
    if any(kw in lower for kw in ("show logs","logs today","logs this week","logs this month","logs this year","logs")):
        period = "year" if "year" in lower else "month" if "month" in lower else "week" if "week" in lower else "day"
        return get_log_history(period)

    _last_bot = next((t.get("content","") for t in reversed(history) if t.get("role") == "assistant"), "")
    if any(m in _last_bot.lower() for m in ("which report would you like","no report files found for")):
        result = skill_lookup_report(message.strip())
        if not result.startswith("No reports found"):
            return result
        return f"No records found matching **'{message.strip()}'**."

    _GEN_BARE = _re_ai.match(r"^(?:generate|create|produce|run|show|list)\s+(?:all\s+)?reports?$", lower.strip(), _re_ai.IGNORECASE)
    _GEN_FOR  = _re_ai.match(r"^(?:generate|create|produce|get|download|run)\s+(?:me\s+)?reports?\s+(?:for\s+)?(.+)$", lower.strip(), _re_ai.IGNORECASE)
    _last_bot_lower = _last_bot.lower()

    if any(m in _last_bot_lower for m in ("which file type would you like", "word, excel, or json")):
        ft_map = {"word":"word","doc":"word","docx":"word","excel":"excel","xlsx":"excel","json":"json"}
        chosen = next((v for k, v in ft_map.items() if k in lower.strip()), None)
        if not chosen:
            return "Please specify: **Word**, **Excel**, or **JSON**"
        ref_recover = _re_ai.search(r"\(Ref:\s*([\w\-]+)\)", _last_bot)
        if not ref_recover:
            return "I lost track of which report. Say: **generate report for [name]**"
        return _skill_open_report(ref_recover.group(1).strip(), chosen)

    if any(m in _last_bot_lower for m in ("which person","multiple reports found","did you mean")):
        return (f"Got it — **{message.strip()}**.\nWhich file type?\n  **Word**  |  **Excel**  |  **JSON**")

    if _GEN_BARE:
        return _skill_list_all_reports()
    if _GEN_FOR:
        rq      = _GEN_FOR.group(1).strip()
        rq      = _re_ai.sub(r"\s*(?:please|now|thanks?)\s*$", "", rq, flags=_re_ai.IGNORECASE).strip()
        matches = _find_report_files(rq)
        if not matches:
            return f"No extracted reports found matching **'{rq}'**."
        if len(matches) > 1:
            names = "\n".join(f"  {i+1}. {m['subject']} (Ref: {m['ref']})" for i, m in enumerate(matches))
            return f"Multiple reports found:\n\n{names}\n\nWhich person did you mean?"
        m = matches[0]
        return (f"Found report for **{m['subject']}** (Ref: {m['ref']}).\n\n"
                f"Which file type?\n  **Word** (.docx)  |  **Excel** (.xlsx)  |  **JSON** (.json)")

    _LOOKUP_PATTERNS = [
        r"(?:look\s*up|lookup)\s+(.+)",
        r"show\s+me\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"find\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"tell\s+me\s+about\s+(.+)",
        r"(?:report\s+(?:for|of|on)|info(?:rmation)?\s+(?:for|of|on|about))\s+(.+)",
    ]
    for pat in _LOOKUP_PATTERNS:
        m = _re_ai.match(pat, lower.strip(), _re_ai.IGNORECASE)
        if m:
            query  = _re_ai.sub(r"\s*(?:please|now|thanks?|report|record|details?)\s*$", "",
                                 m.group(1).strip(), flags=_re_ai.IGNORECASE).strip()
            if query and len(query) >= 3:
                result = skill_lookup_report(query)
                if not result.startswith("No reports found"):
                    return result
                return f"No records found matching **'{query}'**."

    cfg = read_config()
    ic  = cfg.get("ica", {})
    ica_ready = all([ic.get("full_cookie"), ic.get("team_id"), ic.get("chat_id")])
    if ica_ready:
        try:
            reply = ica_chat(history, message)
            if _is_hallucinated_reply(reply):
                return ("I can only answer from our extracted records. "
                        "Please use 'look up [name or reference]' to retrieve the report first.")
            return reply
        except Exception as exc:
            return f"⚠ ICA error: {str(exc)[:200]}"

    return (
        "Hi! I'm Bee. I can help with:\n"
        "• 'look up [name]'     — search extracted reports\n"
        "• 'sync'               — sync Box → Local Folder\n"
        "• 'extract'            — run extraction pipeline\n"
        "• 'file status'        — show Pending/Completed counts\n"
        "• 'logs this week'     — view extraction log history\n\n"
        "Configure ICA credentials in config.json to enable full AI responses."
    )


# ── REST endpoint ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("/send")
def chat_send(req: ChatRequest):
    try:
        reply = route_chat_message(req.message, req.history)
        return {"reply": reply}
    except Exception as exc:
        return {"reply": f"⚠ Error: {str(exc)[:300]}"}
