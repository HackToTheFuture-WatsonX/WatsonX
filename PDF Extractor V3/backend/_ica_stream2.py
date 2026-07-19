"""The stream endpoint validates 'entryId' but rejected a valid 24-hex prompt id.
Hypothesis: it wants an ANSWER entry id. Try creating ANSWER stub, then stream it.
Also test alternate param names and no-param baseline."""
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

def req(method, url, body=None, timeout=40, read=500):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            txt = resp.read().decode("utf-8", "replace")
            print(f"  {method} {url.split('/new-chat')[-1][:90]}\n    -> {resp.status} ct={resp.headers.get('Content-Type','')} body[:{read}]={txt[:read]!r}")
            return resp.status, txt, dict(resp.headers)
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        print(f"  {method} {url.split('/new-chat')[-1][:90]}\n    -> HTTP {e.code} body={b[:300]!r}")
        return e.code, b, {}
    except Exception as e:
        print(f"  {method} {url.split('/new-chat')[-1][:90]}\n    -> ERR {e}")
        return None, str(e), {}

# Baseline: stream with no params, and alternate param names using a dummy valid id
print("=== baseline no-param / alt param names ===")
req("GET", f"{base}/chats/{chat_id}/entries/stream", None, read=200)
# post a prompt to get a real id
_, echo, _ = req("POST", f"{base}/chats/{chat_id}/entries",
    {"chatId": chat_id, "type": "PROMPT",
     "content": {"prompt": "Reply with exactly: OK", "promptId": "", "promptUuid": "",
        "isIncludedInContext": True, "sensitiveInformation": {"hasSensitiveInformation": False}}}, read=100)
prompt_id = json.loads(echo).get("_id", "")
print("prompt_id =", prompt_id)

for pname in ("entryId", "id", "entry_id", "promptEntryId", "promptId"):
    req("GET", f"{base}/chats/{chat_id}/entries/stream?{pname}={prompt_id}", None, read=250)
    print("   ---")

# Try creating an ANSWER entry linked to the prompt
print("\n=== create ANSWER entry linked to prompt ===")
for ans_body in [
    {"chatId": chat_id, "type": "ANSWER", "content": {"answer": "", "promptEntryId": prompt_id}},
    {"chatId": chat_id, "type": "ANSWER", "promptEntryId": prompt_id, "content": {"answer": ""}},
]:
    st, txt, _ = req("POST", f"{base}/chats/{chat_id}/entries", ans_body, read=300)
    if st == 200 or st == 201:
        try:
            aid = json.loads(txt).get("_id", "")
            print("   ANSWER entry id =", aid)
            if aid:
                req("GET", f"{base}/chats/{chat_id}/entries/stream?entryId={aid}", None, timeout=40, read=800)
        except Exception as e:
            print("   parse err", e)
    print("   ---")
