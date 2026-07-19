"""
viewer.py — Browse extracted output files for PDF Extractor V3.
Ported from ViewExtractedFrame.on_show (pdf_extractor_ui_v2.py lines 1391–1473).
"""
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter
from config import extracted_folder

router = APIRouter(prefix="/api/view", tags=["view"])

_TYPES = [
    ("Word Documents",  "Word Extracts",      ".docx"),
    ("Excel Workbooks", "CSV Extracts",        ".xlsx"),
    ("JSON Files",      "JSON File Extracts",  ".json"),
]


@router.get("/files")
def view_files():
    """Return extracted files grouped by type and reference subfolder."""
    ext_root = extracted_folder()
    sections = []

    for label, subfolder_name, ext in _TYPES:
        base  = ext_root / subfolder_name
        files = sorted(
            (f for f in base.rglob("*.*") if f.suffix.lower() == ext),
            key=lambda p: p.stat().st_mtime, reverse=True
        ) if base.exists() else []

        # Group by ref subfolder (parent folder name)
        groups: dict[str, list] = {}
        for f in files:
            key = f.parent.name
            groups.setdefault(key, []).append({
                "name":  f.name,
                "path":  str(f),
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

        sections.append({
            "label":   label,
            "type":    subfolder_name,
            "ext":     ext,
            "count":   len(files),
            "groups":  [
                {"ref": ref_key, "files": file_list}
                for ref_key, file_list in groups.items()
            ],
        })

    total = sum(s["count"] for s in sections)
    return {"sections": sections, "total": total}


@router.post("/open")
def view_open(body: dict):
    """Open a file in the OS default application (Windows)."""
    path = body.get("path", "")
    if not path or not Path(path).exists():
        return {"status": "error", "message": "File not found"}
    try:
        os.startfile(path)
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
