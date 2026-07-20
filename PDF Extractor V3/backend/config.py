"""
config.py — Config and path helpers for PDF Extractor V3 backend.

Persistence is now SQLite (see db.py) — the database is the single source of
truth for config, tracking, JWT config, and extraction logs. The public function
signatures below (read_config, write_config, load_tracking wrappers, etc.) are
preserved as thin wrappers over db.py so existing call sites work unchanged.

Path resolution:
  In development: the SQLite DB lives next to main.py (backend/).
  In a packaged Electron build: it lives in the user's data dir
    (%APPDATA%/PDF Extractor V3/) — passed in via --data-dir CLI arg from main.js.
"""
import json
from pathlib import Path

import db

# BASE_DIR = directory containing this file (backend/ or PyInstaller _MEIPASS)
BASE_DIR = Path(__file__).parent.resolve()

# DATA_DIR: where the SQLite DB lives.
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


def _log_history_dir() -> Path:
    return _data_dir() / LOG_HISTORY_DIR_REL


# Expose these as module-level names so other modules can import them directly
# (they are properties — re-evaluated each call)
def LOG_HISTORY_DIR() -> Path: return _log_history_dir()


def read_config() -> dict:
    """Return the full config dict from the database.

    Raises FileNotFoundError when no config has been saved yet, mirroring the
    legacy behaviour so callers that expect configuration to exist still fail
    loudly."""
    if not db.config_exists():
        raise FileNotFoundError(
            "No configuration found in the database.\n"
            "Open the Settings page and save your credentials to create it."
        )
    return db.config_get_all()


def write_config(cfg: dict) -> str:
    """Persist the full config dict to the database. Returns the DB path (str)
    for backward-compat with callers that logged the returned path."""
    db.config_replace_all(cfg)
    return str(db._db_path())


def read_config_safe() -> dict:
    """Like read_config() but returns a full default template merged with any
    stored values instead of raising when nothing is stored yet (Settings page)."""
    if not db.config_exists():
        return default_config()
    return db.config_get_all()


def default_config() -> dict:
    """Return a fresh config template with all keys present and empty values."""
    return {
        "pdf_password": "",
        "box": {
            "folder_id": "",
            "archive_folder_id": "",
            "output_folder_id": "",
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


def write_jwt_config(raw_json: str) -> str:
    """Validate + save the Box JWT config JSON to the database.
    Returns a descriptive location string for backward-compat."""
    parsed = json.loads(raw_json)  # raises json.JSONDecodeError if invalid
    db.jwt_config_set(parsed)
    return f"{db._db_path()} (jwt_config)"


def jwt_config_exists() -> bool:
    """Whether a Box JWT config has been stored in the database."""
    return db.jwt_config_exists()


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
