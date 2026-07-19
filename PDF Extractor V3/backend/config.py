"""
config.py — Config and path helpers for PDF Extractor V3 backend.

In development: config.json lives next to main.py (backend/).
In a packaged Electron build: config.json lives in the user's data dir
  (%APPDATA%/PDF Extractor V3/) — passed in via --data-dir CLI arg from main.js.
"""
import json
import os
from pathlib import Path

# BASE_DIR = directory containing this file (backend/ or PyInstaller _MEIPASS)
BASE_DIR = Path(__file__).parent.resolve()

# DATA_DIR: where config.json + tracking_db.json live.
# Overridden by --data-dir argument in main.py's argparse;
# defaults to BASE_DIR so development works without any extra args.
_DATA_DIR: Path | None = None

LOG_HISTORY_DIR_REL = "Log History"


def set_data_dir(path: str | Path) -> None:
    """Called from main.py after parsing --data-dir arg."""
    global _DATA_DIR
    _DATA_DIR = Path(path)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _data_dir() -> Path:
    if _DATA_DIR is not None:
        return _DATA_DIR
    return BASE_DIR


def _config_path() -> Path:
    return _data_dir() / "config.json"


def _tracking_path() -> Path:
    return _data_dir() / "tracking_db.json"


def _log_history_dir() -> Path:
    return _data_dir() / LOG_HISTORY_DIR_REL


# Expose these as module-level names so other modules can import them directly
# (they are properties — re-evaluated each call)
def CONFIG_PATH() -> Path:   return _config_path()
def TRACKING_PATH() -> Path: return _tracking_path()
def LOG_HISTORY_DIR() -> Path: return _log_history_dir()


def read_config() -> dict:
    p = _config_path()
    if not p.exists():
        # Fallback: try BASE_DIR (useful in development)
        fallback = BASE_DIR / "config.json"
        if fallback.exists():
            p = fallback
        else:
            raise FileNotFoundError(
                f"config.json not found at {p}\n"
                "Copy config.json from the backend/ template directory and fill in your credentials."
            )
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_config(cfg: dict) -> Path:
    """Atomically write the full config dict to config.json in the data dir."""
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)
    return p


def read_config_safe() -> dict:
    """Like read_config() but returns an empty template instead of raising
    when config.json does not exist yet (used by the Settings page)."""
    try:
        return read_config()
    except FileNotFoundError:
        return default_config()


def default_config() -> dict:
    """Return a fresh config template with all keys present and empty values."""
    return {
        "pdf_password": "",
        "box": {
            "folder_id": "",
            "archive_folder_id": "",
            "output_folder_id": "",
            "jwt_config_file": "box_jwt_config.json",
        },
        "local": {
            "local_folder": "Local Folder",
            "extracted_folder": "Local Folder/Extracted",
            "archive_folder": "Local Folder/Archive",
        },
        "sync": {
            "auto_sync_enabled": False,
            "auto_sync_interval_minutes": 30,
        },
        "ica": {
            "full_cookie": "",
            "team_id": "",
            "team_name": "",
            "assistant_id": "",
            "chat_id": "",
            "base_url": "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat",
        },
        "settings": {
            "search_subfolders": True,
            "file_extension": ".pdf",
            "overwrite_existing_exports": False,
            "log_activity": True,
            "chat_enabled": False,
        },
    }


def jwt_config_path() -> Path:
    """Path where the Box JWT config JSON should be saved (next to config.json)."""
    cfg = read_config_safe()
    fname = cfg.get("box", {}).get("jwt_config_file", "box_jwt_config.json")
    return _data_dir() / fname


def write_jwt_config(raw_json: str) -> Path:
    """Validate + save the Box JWT config JSON to the data dir."""
    parsed = json.loads(raw_json)  # raises json.JSONDecodeError if invalid
    p = jwt_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    return p


def local_folder() -> Path:

    cfg = read_config()
    rel = cfg.get("local", {}).get("local_folder", "Local Folder")
    path = Path(rel) if Path(rel).is_absolute() else _data_dir() / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def extracted_folder() -> Path:
    cfg = read_config()
    rel = cfg.get("local", {}).get("extracted_folder", "Local Folder/Extracted")
    path = Path(rel) if Path(rel).is_absolute() else _data_dir() / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def archive_folder() -> Path:
    cfg = read_config()
    rel = cfg.get("local", {}).get("archive_folder", "Local Folder/Archive")
    path = Path(rel) if Path(rel).is_absolute() else _data_dir() / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def ai_json_dir() -> Path:
    return extracted_folder() / "JSON File Extracts"
