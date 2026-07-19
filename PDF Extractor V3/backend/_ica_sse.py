"""Confirmed: POST ANSWER entry with promptEntryId returns SSE stream with the answer.
Capture full SSE to understand format for parsing."""
import json, urllib.request, urllib.error, os

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

def post(url, body, timeout=90):
    data = json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    resp = urllib.request.urlopen(r, timeout=timeout)
    return resp

purl = f"{base}/chats/{chat_id}/entries"
# 1) PROMPT
p = post(purl, {"chatId": chat_id, "type": "PROMPT",
    "content": {"prompt": "Reply with exactly the word OK and nothing else.", "promptId": "", "promptUuid": "",
        "isIncludedInContext": True, "sensitiveInformation": {"hasSensitiveInformation": False}}})
echo = json.loads(p.read().decode("utf-8"))
prompt_id = echo["_id"]
print("prompt_id =", prompt_id)

# 2) ANSWER (triggers SSE)
resp = post(purl, {"chatId": chat_id, "type": "ANSWER", "content": {"answer": "", "promptEntryId": prompt_id}})
print("status:", resp.status, "ct:", resp.headers.get("Content-Type"))
print("=== RAW SSE (first 4000 chars) ===")
raw = resp.read().decode("utf-8", "replace")
print(repr(raw[:4000]))
print("=== TAIL (last 1500) ===")
print(repr(raw[-1500:]))
