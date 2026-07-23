"""
settings.py — Configuration management REST API for PDF Extractor V3.

Lets the React Settings page read and write config.json (credentials, paths,
sync + extraction options), upload the Box JWT config JSON, and test the Box
and ICA connections — all without hand-editing config.json.

Endpoints:
    GET  /api/settings              → current config (secrets masked)
    POST /api/settings              → save config (partial deep-merge)
    GET  /api/settings/status       → which credential groups are configured
    POST /api/settings/jwt          → upload/replace Box JWT config JSON
    POST /api/settings/test/box     → test Box JWT connection
    POST /api/settings/test/ica     → test ICA cookie/team/chat connection
"""
import json
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import activity
from config import (
    read_config_safe, write_config, default_config,
    jwt_config_exists, write_jwt_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Keys whose values should never be sent back to the frontend in cleartext.
# We return a boolean-ish marker instead so the UI can show "configured".
_SECRET_PATHS = [
    ("pdf_password",),
    ("ica", "full_cookie"),
]


_MASK = "••••••••"


def _get_path(cfg: dict, path: tuple) -> Any:
    cur: Any = cfg
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _set_path(cfg: dict, path: tuple, value: Any) -> None:
    cur = cfg
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def _mask_config(cfg: dict) -> dict:
    """Return a deep copy of cfg with secret values replaced by a mask marker
    (only if they are non-empty)."""
    masked = json.loads(json.dumps(cfg))  # deep copy
    for path in _SECRET_PATHS:
        val = _get_path(masked, path)
        if isinstance(val, str) and val.strip():
            _set_path(masked, path, _MASK)
    masked.pop("_comment", None)
    return masked


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge patch into base. Values equal to the mask marker are
    treated as 'unchanged' and skipped so we never overwrite a real secret
    with the mask string."""
    for key, val in patch.items():
        if val == _MASK:
            continue  # keep existing secret
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


# ── Models ────────────────────────────────────────────────────────────────────
class ConfigPatch(BaseModel):
    config: dict


class JwtUpload(BaseModel):
    content: str  # raw JSON text of the Box JWT config file


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.get("")
def get_settings():
    cfg = read_config_safe()
    # Ensure all default keys exist so the form always has fields to bind to
    merged = default_config()
    _deep_merge(merged, cfg)
    return {"config": _mask_config(merged)}


@router.post("")
def save_settings(patch: ConfigPatch):
    current = read_config_safe()
    prev_chat_id = current.get("ica", {}).get("chat_id", "")

    # Start from defaults so missing sections get created, then existing, then patch
    merged = default_config()
    _deep_merge(merged, current)
    _deep_merge(merged, patch.config)
    # Trim the ICA cookie in case the textarea introduced leading/trailing
    # whitespace or newlines (which would cause HTTP 400/403 from ICA's gateway).
    ica = merged.get("ica", {})
    if isinstance(ica.get("full_cookie"), str):
        ica["full_cookie"] = ica["full_cookie"].strip()
    # If chat_id changed, the previous priming is no longer valid — reset the
    # marker so the UI shows "Not yet primed" and Initialize is required again.
    if ica.get("chat_id", "") != prev_chat_id:
        ica["system_prompt_chat_id"] = ""
    path = write_config(merged)

    # Log which top-level sections changed. We diff on masked values so a saved
    # config never leaks the real secrets into the activity log.
    changed = _diff_sections(_mask_config(current), _mask_config(merged))
    if changed:
        activity.write(
            "SETTINGS",
            "Settings saved — updated section(s): " + ", ".join(sorted(changed)),
            level="info",
        )

    return {"status": "saved", "path": str(path), "config": _mask_config(merged)}


def _diff_sections(before: dict, after: dict) -> set[str]:
    """Return the set of top-level keys whose (masked) content differs."""
    keys = set(before.keys()) | set(after.keys())
    return {k for k in keys if before.get(k) != after.get(k)}


@router.get("/status")
def settings_status():
    cfg = read_config_safe()
    box = cfg.get("box", {})
    ica = cfg.get("ica", {})
    jwt_exists = jwt_config_exists()

    box_ok = bool(box.get("folder_id")) and jwt_exists
    ica_ok = bool(ica.get("full_cookie")) and bool(ica.get("team_id")) and bool(ica.get("chat_id"))
    pdf_ok = bool(cfg.get("pdf_password"))

    return {
        "box": {
            "configured": box_ok,
            "jwt_uploaded": jwt_exists,
            "folder_id": bool(box.get("folder_id")),
        },
        "ica": {
            "configured": ica_ok,
            "full_cookie": bool(ica.get("full_cookie")),
            "team_id": bool(ica.get("team_id")),
            "chat_id": bool(ica.get("chat_id")),
            "system_prompt_chat_id": ica.get("system_prompt_chat_id", ""),
            "primed": bool(ica.get("chat_id")) and
                      ica.get("chat_id") == ica.get("system_prompt_chat_id"),
        },
        "pdf_password": pdf_ok,
        "ready": box_ok,  # minimum needed to sync + extract
    }


@router.post("/jwt")
def upload_jwt(payload: JwtUpload):
    try:
        path = write_jwt_config(payload.content)
    except json.JSONDecodeError as e:
        activity.write("JWT-UPLOAD", f"Box JWT upload rejected — invalid JSON: {e}",
                       level="error")
        return {"status": "error", "error": f"Invalid JSON: {e}"}
    except Exception as e:  # noqa: BLE001
        activity.write("JWT-UPLOAD", f"Box JWT upload failed: {e}", level="error")
        return {"status": "error", "error": str(e)}
    activity.write("JWT-UPLOAD", "Box JWT service-account config saved.",
                   level="info")
    return {"status": "saved", "path": str(path)}


@router.post("/test/box")
def test_box():
    try:
        from box_client import get_box_client
        client, cfg = get_box_client()
        user = client.user().get()
        folder_id = cfg.get("box", {}).get("folder_id", "0")
        folder = client.folder(folder_id).get()
        user_login = getattr(user, "login", getattr(user, "name", "unknown"))
        folder_name = getattr(folder, "name", folder_id)
        activity.write("BOX-TEST",
                       f"Box connection OK — user={user_login}, folder={folder_name!r}.",
                       level="info")
        return {
            "status": "ok",
            "user": user_login,
            "folder": folder_name,
        }
    except Exception as e:  # noqa: BLE001
        activity.write("BOX-TEST", f"Box connection failed: {e}", level="error")
        return {"status": "error", "error": str(e)}


@router.post("/test/ica")
def test_ica():
    try:
        from chat import ica_chat
        reply = ica_chat([], "Hi Bee")
        activity.write("ICA-TEST",
                       f'ICA test OK — reply preview: {(reply or "(empty)")[:200]}',
                       level="info")
        return {"status": "ok", "reply_preview": (reply or "")[:120]}
    except Exception as e:  # noqa: BLE001
        activity.write("ICA-TEST", f"ICA test failed: {e}", level="error")
        return {"status": "error", "error": str(e)}


# ── Streaming connection tests (Server-Sent Events) ───────────────────────────
#
# GET so they can be consumed by the browser's EventSource. Each SSE message is
# a JSON object: {"step": "...", "state": "run|ok|error|done", ...}. The stream
# ends after a "done" (success) or "error" (failure) event.

def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _stream_from(generator_factory):
    """Wrap a step-generator so any unexpected error still surfaces to the UI
    as a terminal 'error' SSE event rather than silently killing the stream."""
    try:
        gen = generator_factory()
        for step in gen:
            yield _sse_event(step)
    except Exception as e:  # noqa: BLE001
        yield _sse_event({"step": "Test failed unexpectedly.", "state": "error",
                          "error": str(e)[:300]})


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering so events arrive live
}


@router.get("/test/box/stream")
def test_box_stream_endpoint():
    from chat import test_box_stream
    return StreamingResponse(
        _stream_from(test_box_stream),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/test/ica/stream")
def test_ica_stream_endpoint():
    from chat import test_ica_stream
    return StreamingResponse(
        _stream_from(test_ica_stream),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/init/ica/stream")
def init_ica_stream_endpoint():
    """Prime the ICA chat by sending bee_prompt.md as the first PROMPT.

    Streams progress via Server-Sent Events. On success, config.ica.
    system_prompt_chat_id is updated so the UI shows "primed" for this chat_id.
    """
    from chat import initialize_ica_system_prompt
    return StreamingResponse(
        _stream_from(initialize_ica_system_prompt),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
