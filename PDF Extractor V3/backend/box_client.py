"""
box_client.py — Box JWT client factory and upload helpers for PDF Extractor V3.
Ported from pdf_extractor_ui_v2.py (lines 246–464).
"""
from pathlib import Path
from config import BASE_DIR, read_config
import db


def _resolve_jwt_path(box_cfg: dict) -> Path:
    """Legacy on-disk fallback lookup for a Box JWT config file.

    Only used when no JWT config is stored in the database (e.g. an older
    install). New installs store the JWT JSON in SQLite via db.jwt_config_set().
    """
    jwt_filename = box_cfg.get("jwt_config_file", "box_jwt_config.json")
    candidates = [
        BASE_DIR / jwt_filename,
        BASE_DIR.parent / "WatsonX Challenge - Web" / jwt_filename,
        BASE_DIR / ".." / "WatsonX Challenge - Web" / jwt_filename,
    ]
    jwt_path = next((p.resolve() for p in candidates if p.exists()), None)
    if jwt_path is None:
        raise FileNotFoundError(
            f"Box JWT config file '{jwt_filename}' not found.\n"
            f"Looked in: {[str(p.resolve()) for p in candidates]}\n"
            "Upload it on the Settings page (it is stored in the database), or "
            "download it from app.box.com/developers/console → your app → Configuration → "
            "App Settings → Generate a Public/Private Keypair."
        )
    return jwt_path


def get_box_client():
    """Build a Box JWT client. Returns (client, cfg).

    The JWT service-account JSON is loaded from the database (single source of
    truth). Falls back to the legacy on-disk file lookup for older installs.
    """
    from boxsdk import JWTAuth, Client
    cfg = read_config()
    box = cfg["box"]

    jwt_dict = db.jwt_config_get()
    if jwt_dict:
        auth = JWTAuth.from_settings_dictionary(jwt_dict)
    else:
        jwt_path = _resolve_jwt_path(box)
        auth     = JWTAuth.from_settings_file(str(jwt_path))
    return Client(auth), cfg



def _box_get_or_create_subfolder(client, parent_folder_id: str, name: str) -> str:
    items = list(client.folder(parent_folder_id).get_items(limit=1000))
    for item in items:
        if item.type == "folder" and item.name == name:
            return item.id
    new_folder = client.folder(parent_folder_id).create_subfolder(name)
    return new_folder.id


def upload_file_to_box(local_path: Path, box_root_folder_id: str,
                       client=None, extracted_root: Path = None) -> str:
    """
    Upload local_path to Box mirroring the dated hierarchy.
    Returns the Box file ID of the uploaded/versioned file.
    """
    if client is None:
        client, _ = get_box_client()

    folder_id = box_root_folder_id
    if extracted_root is not None:
        try:
            rel        = local_path.relative_to(extracted_root)
            path_parts = list(rel.parts[1:-1])
            for part in path_parts:
                folder_id = _box_get_or_create_subfolder(client, folder_id, part)
        except ValueError:
            pass

    existing = {
        item.name: item.id
        for item in client.folder(folder_id).get_items(limit=1000)
        if item.type == "file"
    }
    if local_path.name in existing:
        uploaded = client.file(existing[local_path.name]).update_contents(str(local_path))
    else:
        uploaded = client.folder(folder_id).upload(str(local_path))
    return uploaded.id
