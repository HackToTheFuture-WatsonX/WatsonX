"""
box_client.py — Box JWT client factory and upload helpers for PDF Extractor V3.
Ported from pdf_extractor_ui_v2.py (lines 246–464).
"""
from pathlib import Path
from config import read_config
import db



def get_box_client():
    """Build a Box JWT client. Returns (client, cfg).

    The JWT service-account JSON is the single source of truth — loaded
    exclusively from the SQLite database via db.jwt_config_get().
    Upload the JWT JSON on the Settings page to configure Box access.
    """
    from boxsdk import JWTAuth, Client
    cfg      = read_config()
    jwt_dict = db.jwt_config_get()
    if not jwt_dict:
        raise FileNotFoundError(
            "No Box JWT config found in the database.\n"
            "Upload it on the Settings page (Settings → Box JWT Config).\n"
            "Download it from app.box.com/developers/console → your app → "
            "Configuration → App Settings → Generate a Public/Private Keypair."
        )
    auth = JWTAuth.from_settings_dictionary(jwt_dict)
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
