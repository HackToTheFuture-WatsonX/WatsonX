"""Inspect the exact POST echo response and the created PROMPT entry structure."""
import json, urllib.request, urllib.error, time, os

DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "pdf-extractor-v3")
CFG = os.path.join(DATA_DIR, "config.json")
with open(CFG, "r", encoding="utf-8") as f:
    cfg = json.load(f)
ic = cfg["ica"]
cookie = ic["full_cookie"]
team_id = ic["team_id"]
team_name = ic["team_name"]
chat_id = ic["chat_id"]
base = ic["base_url"].rstrip("/")

hdr = {
    "cookie": cookie, "teamid": team_id, "teamname": team_name,
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}

url = f"{base}/chats/{chat_id}/entries"
payload = json.dumps({
    "chatId": chat_id, "type": "PROMPT",
    "content": {"prompt": "Reply with the single word OK.", "promptId": "", "promptUuid": "",
        "isIncludedInContext": True,
        "sensitiveInformation": {"hasSensitiveInformation": False}},
}).encode("utf-8")

print("=== POST echo ===")
req = urllib.request.Request(url, data=payload, headers=hdr, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        echo = json.loads(r.read().decode("utf-8"))
        print(json.dumps(echo, indent=2)[:3000])
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode("utf-8", "replace")[:1000])
    raise SystemExit

print("\n=== poll 40s, dump ALL entries structure once ANSWER appears or timeout ===")
ghdr = {k: v for k, v in hdr.items() if k != "Content-Type"}
for i in range(20):
    time.sleep(2)
    greq = urllib.request.Request(url, headers=ghdr, method="GET")
    try:
        with urllib.request.urlopen(greq, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("poll err", e.code); continue
    entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
    types = [e.get("type") for e in entries]
    print(f"[{i}] {len(entries)} entries: {types}")
    ans = [e for e in entries if e.get("type") == "ANSWER"]
    if ans:
        print("ANSWER FOUND:", json.dumps(ans[-1], indent=2)[:1500])
        break
else:
    print("\nNO ANSWER. Dumping last PROMPT entry structure:")
    prompts = [e for e in entries if e.get("type") == "PROMPT"]
    if prompts:
        print(json.dumps(prompts[-1], indent=2)[:2000])
