"""Found it: GET /entries/stream needs entryId. Discover exact shape & trigger a real answer."""
import json, urllib.request, urllib.error, os, time

DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "pdf-extractor-v3")
with open(os.path.join(DATA_DIR, "config.json"), "r", encoding="utf-8") as f:
    cfg = json.load(f)
ic = cfg["ica"]
cookie, team_id, team_name = ic["full_cookie"], ic["team_id"], ic["team_name"]
chat_id = ic["chat_id"]
base = ic["base_url"].rstrip("/")

hdr = {
    "cookie": cookie, "teamid": team_id, "teamname": team_name,
    "Content-Type": "application/json",
    "Accept": "text/event-stream, application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}

def req(method, url, body=None, timeout=40, read=400):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            txt = resp.read().decode("utf-8", "replace")
            print(f"  {method} {url}\n    -> {resp.status} ct={resp.headers.get('Content-Type','')}\n    body[:{read}]={txt[:read]!r}")
            return resp.status, txt
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        print(f"  {method} {url}\n    -> HTTP {e.code} body={b[:400]!r}")
        return e.code, b
    except Exception as e:
        print(f"  {method} {url}\n    -> ERR {e}")
        return None, str(e)

# 1) POST a fresh prompt, capture its entry _id
print("=== POST prompt ===")
purl = f"{base}/chats/{chat_id}/entries"
payload = {"chatId": chat_id, "type": "PROMPT",
    "content": {"prompt": "Reply with exactly: OK", "promptId": "", "promptUuid": "",
        "isIncludedInContext": True, "sensitiveInformation": {"hasSensitiveInformation": False}}}
_, echo_txt = req("POST", purl, payload, read=400)
try:
    entry_id = json.loads(echo_txt).get("_id", "")
except Exception:
    entry_id = ""
print("entry_id =", entry_id)

if entry_id:
    print("\n=== Try stream trigger variants with entryId ===")
    variants = [
        ("GET", f"{base}/chats/{chat_id}/entries/stream?entryId={entry_id}", None),
        ("GET", f"{base}/chats/{chat_id}/entries/{entry_id}/stream", None),
        ("POST", f"{base}/chats/{chat_id}/entries/{entry_id}/stream", {}),
        ("POST", f"{base}/chats/{chat_id}/entries/stream", {"entryId": entry_id}),
    ]
    for m, u, b in variants:
        req(m, u, b, timeout=40, read=600)
        print("   ---")
