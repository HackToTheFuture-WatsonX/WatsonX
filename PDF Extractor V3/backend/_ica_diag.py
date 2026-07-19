"""Ad-hoc ICA connection diagnostic — uses the packaged app's saved config.

Reproduces the exact test_ica_stream request against the live ICA endpoint,
prints the raw POST response, then polls a handful of times printing the
full entry list (types + ids + timestamps) so we can see whether an ANSWER
ever arrives for the configured chat.

Run:  python _ica_diag.py
"""
import json
import time
import urllib.request
import urllib.error
import urllib.parse as _urlparse
from pathlib import Path

CONFIG = Path(r"C:\Users\nielr\AppData\Roaming\pdf-extractor-v3\config.json")


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    ic = cfg.get("ica", {})
    cookie = (ic.get("full_cookie", "") or "").strip()
    team_id = ic.get("team_id", "")
    team_name = ic.get("team_name", "")
    chat_id = ic.get("chat_id", "")
    assistant_id = ic.get("assistant_id", "")
    base_url = ic.get(
        "base_url",
        "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat",
    ).rstrip("/")

    print(f"team_id={team_id!r}  team_name={team_name!r}")
    print(f"assistant_id={assistant_id!r}  chat_id={chat_id!r}")
    print(f"cookie_len={len(cookie)}")
    print(f"base_url={base_url}")

    url = f"{base_url}/chats/{chat_id}/entries"
    prompt = "ping — connection test"
    payload = json.dumps({
        "chatId": chat_id, "type": "PROMPT",
        "content": {
            "prompt": prompt, "promptId": "", "promptUuid": "",
            "isIncludedInContext": True,
            "sensitiveInformation": {"hasSensitiveInformation": False},
        },
    }).encode("utf-8")
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

    print(f"\n=== POST {url} ===")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    posted_id = ""
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            print(f"HTTP {resp.status}")
            try:
                echo = json.loads(body)
                posted_id = echo.get("_id", "") if isinstance(echo, dict) else ""
                print("POST response:", json.dumps(echo, indent=2)[:1500])
            except Exception:
                print("POST body (raw):", body[:1500])
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode('utf-8', 'replace')[:1000]}")
        return
    except Exception as exc:
        print(f"UNREACHABLE: {exc}")
        return

    print(f"\nposted entry _id = {posted_id!r}")

    poll_url = url
    get_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
    for attempt in range(1, 16):  # ~30s
        time.sleep(2)
        try:
            preq = urllib.request.Request(poll_url, headers=get_headers, method="GET")
            with urllib.request.urlopen(preq, timeout=30) as pr:
                data = json.loads(pr.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"poll {attempt}: HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
            continue
        except Exception as exc:
            print(f"poll {attempt}: error {exc}")
            continue
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        summary = [
            {
                "type": e.get("type"),
                "_id": e.get("_id", "")[:8],
                "status": e.get("status"),
                "created": e.get("createdAt") or e.get("created_at"),
            }
            for e in entries
        ] if isinstance(entries, list) else entries
        print(f"poll {attempt}: {len(entries) if isinstance(entries, list) else '?'} entries")
        print("   ", summary)
        # Print full content of any ANSWER
        for e in (entries if isinstance(entries, list) else []):
            if e.get("type") == "ANSWER":
                print("   ANSWER content:", json.dumps(e.get("content", {}), indent=2)[:800])


if __name__ == "__main__":
    main()
