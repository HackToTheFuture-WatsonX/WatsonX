"""Inspect the ICA chat's SWITCH_MODEL entry and a sample PROMPT entry to
understand why no ANSWER is being generated. Delete after use.
"""
import json, os, urllib.request, urllib.error
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

headers = {
    "cookie": cookie,
    "teamid": _urlparse.quote(team_id, safe=""),
    "teamname": _urlparse.quote(team_name, safe=""),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}

def get(url):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as pr:
        return json.loads(pr.read().decode("utf-8"))

# 1) The chat's entries — dump SWITCH_MODEL + last PROMPT fully
url = f"{base_url}/chats/{chat_id}/entries"
data = get(url)
entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
print(f"=== {len(entries)} entries ===")
for e in entries:
    if e.get("type") == "SWITCH_MODEL":
        print("\n--- SWITCH_MODEL entry ---")
        print(json.dumps(e, indent=2)[:1500])
        break
# last prompt
prompts = [e for e in entries if e.get("type") == "PROMPT"]
if prompts:
    print("\n--- last PROMPT entry ---")
    print(json.dumps(prompts[-1], indent=2)[:1200])

# 2) The chat object itself (metadata: model, assistant, etc.)
print("\n\n=== chat metadata ===")
for candidate in (
    f"{base_url}/chats/{chat_id}",
    f"{base_url}/chats/{chat_id}/details",
):
    try:
        meta = get(candidate)
        print(f"\n[{candidate}]")
        print(json.dumps(meta, indent=2)[:2000])
    except urllib.error.HTTPError as ex:
        print(f"\n[{candidate}] HTTP {ex.code}: {ex.read().decode('utf-8','replace')[:200]}")
    except Exception as ex:
        print(f"\n[{candidate}] error: {ex}")

# 3) List the team's chats to see if any produce answers / what fields they carry
print("\n\n=== team chats list ===")
for candidate in (
    f"{base_url}/chats",
    f"{base_url}/chats?teamId={team_id}",
):
    try:
        lst = get(candidate)
        print(f"\n[{candidate}]")
        print(json.dumps(lst, indent=2)[:1500])
        break
    except urllib.error.HTTPError as ex:
        print(f"\n[{candidate}] HTTP {ex.code}: {ex.read().decode('utf-8','replace')[:200]}")
    except Exception as ex:
        print(f"\n[{candidate}] error: {ex}")
