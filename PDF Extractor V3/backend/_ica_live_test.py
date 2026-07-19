"""One-shot ICA connection diagnostic against the LIVE packaged config.

Reads the installed app's config.json, reproduces the exact POST-then-poll
that test_ica_stream() performs, and prints everything: HTTP status of the
POST, then on each poll the number of entries and their types, and the final
ANSWER (if any). Delete after use.
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

url = f"{base_url}/chats/{chat_id}/entries"
prompt = "ping — connection test"
print(f"POST {url}")
print(f"team_id={team_id}  team_name={team_name}  chat_id={chat_id}")
print(f"cookie length={len(cookie)}")

headers = {
    "cookie": cookie,
    "teamid": _urlparse.quote(team_id, safe=""),
    "teamname": _urlparse.quote(team_name, safe=""),
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://servicesessentials.ibm.com",
    "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
}

payload = json.dumps({
    "chatId": chat_id, "type": "PROMPT",
    "content": {
        "prompt": prompt, "promptId": "", "promptUuid": "",
        "isIncludedInContext": True,
        "sensitiveInformation": {"hasSensitiveInformation": False},
    },
}).encode("utf-8")

# --- First, GET current entries to see the chat's existing state ---
print("\n=== GET current entries (before POST) ===")
try:
    get_req = urllib.request.Request(
        url, headers={k: v for k, v in headers.items() if k != "Content-Type"}, method="GET")
    with urllib.request.urlopen(get_req, timeout=30) as pr:
        data = json.loads(pr.read().decode("utf-8"))
    entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
    print(f"  {len(entries)} entries, types={[e.get('type') for e in entries]}")
    pre_count = len(entries)
except urllib.error.HTTPError as e:
    print(f"  GET HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")
    pre_count = 0
except Exception as exc:
    print(f"  GET error: {exc}")
    pre_count = 0

# --- POST the prompt ---
print("\n=== POST prompt ===")
req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        print(f"  HTTP {getattr(resp,'status','?')}")
        print(f"  body: {raw[:500]}")
except urllib.error.HTTPError as e:
    print(f"  POST HTTP {e.code}: {e.read().decode('utf-8','replace')[:500]}")
    raise SystemExit(1)
except Exception as exc:
    print(f"  POST error: {exc}")
    raise SystemExit(1)

# --- Poll for an ANSWER ---
print("\n=== Poll for ANSWER (up to 90s) ===")
poll_req_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
for attempt in range(1, 46):
    time.sleep(2)
    try:
        poll_req = urllib.request.Request(url, headers=poll_req_headers, method="GET")
        with urllib.request.urlopen(poll_req, timeout=30) as pr:
            data = json.loads(pr.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  poll {attempt} HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        continue
    except Exception as exc:
        print(f"  poll {attempt} error: {exc}")
        continue
    entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
    types = [e.get("type") for e in entries]
    print(f"  poll {attempt} ({attempt*2}s): {len(entries)} entries, types={types}")
    answers = [e for e in entries if e.get("type") == "ANSWER"]
    if answers:
        last = answers[-1]
        content = last.get("content", {})
        print("\n=== ANSWER entry (full) ===")
        print(json.dumps(last, indent=2)[:2000])
        reply = str(content.get("answer", "")).strip()
        print(f"\n  reply text: {reply[:300]!r}")
        raise SystemExit(0)

print("\n  NO ANSWER after 90s")
