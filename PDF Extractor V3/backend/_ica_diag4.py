"""ICA diagnostic #4 — find the generation/stream trigger.

The POST /entries only stores the PROMPT; something else drives the model to
generate the ANSWER. Probe the endpoints the browser likely calls after
posting a prompt (stream / generate / answer), for the last posted prompt.

Run:  python _ica_diag4.py
"""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

CONFIG = Path(r"C:\Users\nielr\AppData\Roaming\pdf-extractor-v3\config.json")


def _ic():
    return json.loads(CONFIG.read_text(encoding="utf-8")).get("ica", {})


def _headers(ic, post=False):
    h = {
        "cookie": (ic.get("full_cookie", "") or "").strip(),
        "teamid": ic.get("team_id", ""),
        "teamname": ic.get("team_name", ""),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://servicesessentials.ibm.com",
        "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{ic.get('chat_id','')}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
    }
    if post:
        h["Content-Type"] = "application/json"
    return h


def _req(method, url, ic, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(ic, post=(payload is not None)),
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, body[:800]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as exc:
        return None, str(exc)[:200]


def main():
    ic = _ic()
    base = ic.get("base_url", "").rstrip("/")
    chat_id = ic.get("chat_id", "")
    entries_url = f"{base}/chats/{chat_id}/entries"

    # Post a fresh prompt to get an entry id
    st, echo = _req("POST", entries_url, ic, {
        "chatId": chat_id, "type": "PROMPT",
        "content": {"prompt": "Say OK.", "promptId": "", "promptUuid": "",
                    "isIncludedInContext": True,
                    "sensitiveInformation": {"hasSensitiveInformation": False}},
    })
    try:
        eid = json.loads(echo).get("_id", "")
    except Exception:
        eid = ""
    print("POST /entries HTTP", st, "entry_id=", eid)

    # Candidate generation/stream endpoints (GET and POST variants)
    candidates = [
        ("GET",  f"{base}/chats/{chat_id}/stream"),
        ("GET",  f"{base}/chats/{chat_id}/entries/{eid}/stream"),
        ("POST", f"{base}/chats/{chat_id}/entries/{eid}/generate"),
        ("POST", f"{base}/chats/{chat_id}/generate"),
        ("POST", f"{base}/chats/{chat_id}/entries/{eid}/answer"),
        ("GET",  f"{base}/chats/{chat_id}/entries/{eid}"),
        ("POST", f"{base}/chats/{chat_id}/completions"),
        ("GET",  f"{base}/chats/{chat_id}/messages"),
    ]
    for method, url in candidates:
        payload = {} if method == "POST" else None
        st, body = _req(method, url, ic, payload)
        print(f"\n{method} {url.replace(base,'')} -> HTTP {st}")
        print("  ", body[:300])


if __name__ == "__main__":
    main()
