"""List models/assistants available to the ICA team, then try SWITCH_MODEL to a
stable (non tech-preview) model on a fresh chat and see if it answers.
Delete after use.
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
# curatorai root (strip the /chat/new-chat service path) for model catalog calls
root = base_url.split("/services/chat/")[0]  # .../curatorai

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


print("=== Probe model/assistant catalog endpoints ===")
for path in (
    f"{base_url}/models",
    f"{base_url}/models/available",
    f"{root}/services/chat/new-chat/models",
    f"{root}/services/model-registry/models",
    f"{root}/services/chat/new-chat/assistants",
    f"{base_url}/assistants",
    f"{base_url}/teams/{team_id}/models",
):
    st, raw = do("GET", path)
    tag = path.split('/curatorai')[-1]
    print(f"\nGET {tag} -> {st}")
    print(f"   {raw[:400]}")
