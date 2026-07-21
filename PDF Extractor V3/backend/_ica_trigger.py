"""Test whether ICA needs a separate trigger/execute call after POSTing a
PROMPT to make the model generate an ANSWER. Delete after use.

We already know POST /entries returns 200 and appends the prompt, but no
ANSWER is ever generated. This probes candidate "generate"/"execute" endpoints
and payload variants to find what actually triggers answer generation.
"""
import json, os, time, urllib.request, urllib.error
import urllib.parse as _urlparse

CONFIG = os.path.join(os.environ["APPDATA"], "pdf-extractor-v3", "config.json")
with open(CONFIG, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

ic = cfg["ica"]
cookie = ic["full_cookie"].strip()
team_id = ic["team_id"]
team_name = ic["team_name"]
chat_id = ic["chat_id"]
base_url = ic["base_url"].rstrip("/")

base_headers = {
    "cookie": cookie,
    "teamid": team_id,
    "teamname": team_name,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}


def do(method, url, body=None):
    headers = dict(base_headers)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return getattr(resp, "status", "?"), raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return "ERR", str(exc)


def count_answers():
    st, raw = do("GET", f"{base_url}/chats/{chat_id}/entries")
    try:
        data = json.loads(raw)
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        return sum(1 for e in entries if e.get("type") == "ANSWER"), len(entries)
    except Exception:
        return -1, -1


print("Before:", count_answers())

# Candidate trigger endpoints the SPA might call after appending the prompt.
candidates = [
    ("POST", f"{base_url}/chats/{chat_id}/generate", {"chatId": chat_id}),
    ("POST", f"{base_url}/chats/{chat_id}/answer", {"chatId": chat_id}),
    ("POST", f"{base_url}/chats/{chat_id}/entries/generate", {"chatId": chat_id}),
    ("POST", f"{base_url}/chats/{chat_id}/stream", {"chatId": chat_id}),
    ("GET",  f"{base_url}/chats/{chat_id}/stream", None),
    ("POST", f"{base_url}/chats/{chat_id}/execute", {"chatId": chat_id}),
]
for method, url, body in candidates:
    st, raw = do(method, url, body)
    print(f"\n{method} {url.split('/new-chat')[-1]} -> {st}")
    print(f"   {raw[:200]}")

time.sleep(3)
print("\nAfter:", count_answers())
