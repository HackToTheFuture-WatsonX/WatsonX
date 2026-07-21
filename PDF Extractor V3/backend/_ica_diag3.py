"""ICA diagnostic #3 — test answer generation with model context + longer poll.

Two experiments:
  A) POST a prompt with RAW teamid/teamname (exactly like the known-working
     app.py) and poll up to 90s — rules out URL-encoding as the culprit and
     gives the reasoning model more time.
  B) If A yields no ANSWER, POST including modelId/modelUuid in the content
     (some ICA deployments require the model echoed back for generation).

Run:  python _ica_diag3.py
"""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

CONFIG = Path(r"C:\Users\nielr\AppData\Roaming\pdf-extractor-v3\config.json")
MODEL_ID = 1071
MODEL_UUID = "eff0f63b-f6d1-4839-be5f-d7e3804a3ff4"


def _ic():
    return json.loads(CONFIG.read_text(encoding="utf-8")).get("ica", {})


def _headers(ic, post=False):
    h = {
        "cookie": (ic.get("full_cookie", "") or "").strip(),
        "teamid": ic.get("team_id", ""),      # RAW — like app.py
        "teamname": ic.get("team_name", ""),  # RAW — like app.py
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://servicesessentials.ibm.com",
        "Referer": f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{ic.get('chat_id','')}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "sec-fetch-site": "same-origin", "sec-fetch-mode": "cors", "sec-fetch-dest": "empty",
    }
    if post:
        h["Content-Type"] = "application/json"
    return h


def _post(url, ic, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=_headers(ic, post=True), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:600]


def _poll(url, ic, since_id, label, max_polls=45):
    for attempt in range(1, max_polls + 1):
        time.sleep(2)
        req = urllib.request.Request(url, headers=_headers(ic), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            print(f"  [{label}] poll {attempt}: {exc}")
            continue
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        answers = [e for e in entries if e.get("type") == "ANSWER"]
        n_prompt = sum(1 for e in entries if e.get("type") == "PROMPT")
        if attempt % 5 == 0 or answers:
            print(f"  [{label}] poll {attempt}: {len(entries)} entries, "
                  f"{n_prompt} prompts, {len(answers)} answers")
        if answers:
            print(f"  [{label}] ANSWER FOUND:",
                  json.dumps(answers[-1].get("content", {}), indent=2)[:600])
            return True
    print(f"  [{label}] no ANSWER after {max_polls} polls")
    return False


def main():
    ic = _ic()
    base = ic.get("base_url", "").rstrip("/")
    chat_id = ic.get("chat_id", "")
    url = f"{base}/chats/{chat_id}/entries"

    print("=== Experiment A: RAW headers, minimal payload, 90s poll ===")
    st, echo = _post(url, ic, {
        "chatId": chat_id, "type": "PROMPT",
        "content": {"prompt": "Reply with the single word OK.", "promptId": "",
                    "promptUuid": "", "isIncludedInContext": True,
                    "sensitiveInformation": {"hasSensitiveInformation": False}},
    })
    print("POST HTTP", st, "id=", echo.get("_id") if isinstance(echo, dict) else echo)
    if _poll(url, ic, echo.get("_id") if isinstance(echo, dict) else "", "A"):
        return

    print("\n=== Experiment B: payload WITH model context ===")
    st, echo = _post(url, ic, {
        "chatId": chat_id, "type": "PROMPT",
        "modelId": MODEL_ID, "modelUuid": MODEL_UUID,
        "content": {"prompt": "Reply with the single word OK.", "promptId": "",
                    "promptUuid": "", "isIncludedInContext": True,
                    "modelId": MODEL_ID, "modelUuid": MODEL_UUID,
                    "sensitiveInformation": {"hasSensitiveInformation": False}},
    })
    print("POST HTTP", st, "id=", echo.get("_id") if isinstance(echo, dict) else echo)
    _poll(url, ic, echo.get("_id") if isinstance(echo, dict) else "", "B")


if __name__ == "__main__":
    main()
