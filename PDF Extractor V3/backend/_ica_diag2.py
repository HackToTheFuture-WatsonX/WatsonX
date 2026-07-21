"""ICA diagnostic #2 — inspect SWITCH_MODEL content and list chats/models.

Goal: understand why chat 6a5c42fb... never produces an ANSWER.
We dump the full SWITCH_MODEL entry of the configured chat, and try to
list the team's chats and available models/assistants so we can pick a
chat/assistant that actually answers.

Run:  python _ica_diag2.py
"""
import json
import urllib.request
import urllib.error
import urllib.parse as _urlparse
from pathlib import Path

CONFIG = Path(r"C:\Users\nielr\AppData\Roaming\pdf-extractor-v3\config.json")


def _load():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    return cfg.get("ica", {})


def _headers(ic, *, post=False):
    h = {
        "cookie": (ic.get("full_cookie", "") or "").strip(),
        "teamid": ic.get("team_id", ""),
        "teamname": ic.get("team_name", ""),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://servicesessentials.ibm.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
    }
    if post:
        h["Content-Type"] = "application/json"
    return h


def _get(url, ic):
    req = urllib.request.Request(url, headers=_headers(ic), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:600]
    except Exception as exc:
        return None, str(exc)


def main():
    ic = _load()
    base = ic.get("base_url", "").rstrip("/")
    chat_id = ic.get("chat_id", "")

    # 1) Dump full entries of the configured chat, focusing on SWITCH_MODEL
    print("=== Entries of configured chat", chat_id, "===")
    st, data = _get(f"{base}/chats/{chat_id}/entries", ic)
    print("HTTP", st)
    if isinstance(data, (list, dict)):
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        for e in entries:
            if e.get("type") == "SWITCH_MODEL":
                print("SWITCH_MODEL full entry:")
                print(json.dumps(e, indent=2)[:2000])

    # 2) Try to list chats for the team (discover a chat that answers)
    for path in ("/chats", "/chats?limit=50"):
        print(f"\n=== GET {path} ===")
        st, data = _get(f"{base}{path}", ic)
        print("HTTP", st)
        if isinstance(data, (list, dict)):
            chats = data if isinstance(data, list) else data.get("data", data.get("chats", []))
            if isinstance(chats, list):
                for c in chats[:20]:
                    print("  chat", c.get("_id"), "name=", c.get("name"),
                          "model=", c.get("model") or c.get("modelId") or c.get("assistantId"))
            else:
                print(json.dumps(data, indent=2)[:800])
            break
        else:
            print(str(data)[:400])

    # 3) Try to list available models/assistants
    for path in ("/models", "/assistants", "/team/models", "/config"):
        print(f"\n=== GET {path} ===")
        st, data = _get(f"{base}{path}", ic)
        print("HTTP", st)
        print(json.dumps(data, indent=2)[:800] if isinstance(data, (list, dict)) else str(data)[:400])


if __name__ == "__main__":
    main()
