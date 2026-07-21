"""Create a FRESH ICA chat via the API, POST a prompt, and poll for an ANSWER.

If a fresh chat produces an ANSWER while the saved chat_id never does, that
proves the saved chat is in a broken/stale state and the fix is to re-capture
a working chat_id. Delete after use.
"""
import json, os, time, urllib.request, urllib.error

CONFIG = os.path.join(os.environ["APPDATA"], "pdf-extractor-v3", "config.json")
with open(CONFIG, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

ic = cfg["ica"]
cookie = ic["full_cookie"].strip()
team_id = ic["team_id"]
team_name = ic["team_name"]
base_url = ic["base_url"].rstrip("/")

base_headers = {
    "cookie": cookie,
    "teamid": team_id,
    "teamname": team_name,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
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
            return getattr(resp, "status", "?"), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return "ERR", str(exc)


# 1) Create a fresh chat
print("=== Create fresh chat ===")
for body in (
    {"title": "conn test", "teamId": team_id},
    {"teamId": team_id},
    {},
):
    st, raw = do("POST", f"{base_url}/chats", body)
    print(f"POST /chats body={body} -> {st}")
    print(f"   {raw[:300]}")
    if st in (200, 201):
        try:
            new_chat = json.loads(raw)
            new_id = new_chat.get("_id") or new_chat.get("chatId")
            if new_id:
                break
        except Exception:
            pass
else:
    print("Could not create a fresh chat; stopping.")
    raise SystemExit(1)

print(f"\nNew chat id: {new_id}")

# 2) POST a prompt to the fresh chat
prompt = "Reply with the single word OK."
payload = {
    "chatId": new_id, "type": "PROMPT",
    "content": {"prompt": prompt, "promptId": "", "promptUuid": "",
                "isIncludedInContext": True,
                "sensitiveInformation": {"hasSensitiveInformation": False}},
}
st, raw = do("POST", f"{base_url}/chats/{new_id}/entries", payload)
print(f"\nPOST prompt -> {st}: {raw[:200]}")

# 3) Poll for an ANSWER
print("\n=== Poll fresh chat ===")
for attempt in range(1, 31):
    time.sleep(2)
    st, raw = do("GET", f"{base_url}/chats/{new_id}/entries")
    try:
        data = json.loads(raw)
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
    except Exception:
        print(f"  poll {attempt} bad json: {raw[:120]}")
        continue
    types = [e.get("type") for e in entries]
    print(f"  poll {attempt} ({attempt*2}s): types={types}")
    answers = [e for e in entries if e.get("type") == "ANSWER"]
    if answers:
        print("\n=== ANSWER ===")
        print(json.dumps(answers[-1], indent=2)[:1500])
        print(f"\nWorking chat_id = {new_id}")
        raise SystemExit(0)

print("\nFresh chat also produced NO ANSWER.")
