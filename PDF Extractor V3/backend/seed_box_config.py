"""
seed_box_config.py — one-shot helper to persist verified Box settings into the
PDF Extractor V3 SQLite DB, then run the same connection test the app runs.

Root cause of "connect wasn't working": the JWT config + folder IDs were never
saved into the DB the app reads, so get_box_client()/read_config() failed. The
credentials and folders themselves are valid.

Usage (dev DB, next to main.py):
    python seed_box_config.py

Usage (production DB in %APPDATA%):
    python seed_box_config.py --data-dir "%APPDATA%\\PDF Extractor V3"
"""
import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import config  # noqa: E402
import db       # noqa: E402

# Verified-good folder IDs (confirmed accessible by the service account).
BOX_FOLDERS = {
    "folder_id":         "398448580241",   # PDF Extracts
    "archive_folder_id": "398464621507",   # Archived Reports
    "output_folder_id":  "398794370345",   # Extracted Files
    "jwt_config_file":   "box_jwt_config.json",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", dest="data_dir", default=None,
                        help="Target data dir (defaults to backend/ dev DB).")
    args = parser.parse_args()

    if args.data_dir:
        config.set_data_dir(args.data_dir)
    db.init_db()

    # 1) Load + store the JWT service-account JSON.
    jwt_path = BASE_DIR / "box_jwt_config.json"
    jwt_raw = jwt_path.read_text(encoding="utf-8")
    config.write_jwt_config(jwt_raw)  # validates JSON + writes to DB
    print(f"[seed] JWT config stored in DB (from {jwt_path.name})")

    # 2) Merge folder IDs into the config (start from defaults, keep any existing).
    cfg = config.default_config()
    if db.config_exists():
        existing = db.config_get_all()
        for k, v in existing.items():
            cfg[k] = v
    cfg.setdefault("box", {})
    cfg["box"].update(BOX_FOLDERS)
    config.write_config(cfg)
    print(f"[seed] Config saved to DB at {db._db_path()}")
    print(f"[seed] box folder_id={cfg['box']['folder_id']} "
          f"archive={cfg['box']['archive_folder_id']} "
          f"output={cfg['box']['output_folder_id']}")

    # 3) Run the SAME test the app's POST /api/settings/test/box performs.
    from box_client import get_box_client
    client, cfg2 = get_box_client()
    user = client.user().get()
    folder = client.folder(cfg2["box"]["folder_id"]).get()
    print(f"[test] OK user={getattr(user, 'login', user.id)} "
          f"folder={folder.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
