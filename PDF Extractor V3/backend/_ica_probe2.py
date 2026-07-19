"""Probe for the real inference trigger. After POSTing a PROMPT, the web UI must
call something to make the model generate. Try streaming variants and entry-linked triggers."""
import json, urllib.request, urllib.error, os

DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "pdf-extractor-v3")
with open(os.path.join(DATA_DIR, "config.json"), "r", encoding="utf-8") as f:
    cfg = json.load(f)
ic = cfg["ica"]
cookie, team_id, team_name = ic["full_cookie"], ic["team_id"], ic["team_name"]
chat_id = ic["chat_id"]
base = ic["base_url"].rstrip("/")
# base = https://servicesessentials.ibm.com/curatorai/services/chat/new-chat
root = base.rsplit("/", 1)[0]  # .../services/chat

hdr = {
    "cookie": cookie, "teamid": team_id, "teamname": team_name,
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}

def try_req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            txt = r.read().decode("utf-8", "replace")
            ct = r.headers.get("Content-Type", "")
            print(f"  {method} {url}\n    -> {r.status} ct={ct} body[:200]={txt[:200]!r}")
            return r.status, txt
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        print(f"  {method} {url}\n    -> HTTP {e.code} body[:200]={b[:200]!r}")
        return e.code, b
    except Exception as e:
        print(f"  {method} {url}\n    -> ERR {e}")
        return None, str(e)

print("=== GET chat metadata (look for model config / generate hints) ===")
try_req("GET", f"{base}/chats/{chat_id}")

print("\n=== Try generation trigger endpoints ===")
# common ICA 1.0 generation patterns
candidates = [
    ("POST", f"{base}/chats/{chat_id}/generate", {}),
    ("POST", f"{base}/chats/{chat_id}/completions", {}),
    ("POST", f"{base}/chats/{chat_id}/entries/stream", {"chatId": chat_id, "type": "PROMPT", "content": {"prompt": "Say OK", "isIncludedInContext": True, "sensitiveInformation": {"hasSensitiveInformation": False}}}),
    ("POST", f"{base}/chats/{chat_id}/response", {}),
    ("POST", f"{base}/chats/{chat_id}/answer", {}),
    ("POST", f"{root}/generate", {"chatId": chat_id}),
    ("GET", f"{base}/chats/{chat_id}/entries/stream", None),
]
for m, u, b in candidates:
    try_req(m, u, b)
