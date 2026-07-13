
"""
Background Check Report Automation V2 — Desktop UI
====================================================
NOTE: To run without a console/terminal window, use Launch.vbs (double-click)
instead of running python pdf_extractor_ui_v2.py directly.
====================================================
Tkinter-based interface for the PDF extraction pipeline — V2 edition.

Key differences from V1:
  • Box folder (folder_id 398448580241) is SYNCED to a local "Local Folder"
    directory first.  The sync can be triggered manually (button) or run
    automatically on a schedule (configurable in config.json).
  • "Check Box" screen replaced by "Scan Folder" — scans the LOCAL folder,
    not Box directly.
  • "Extract Files" reads PDFs from the Local Folder (not Box).
  • All extraction outputs (Word / Excel / JSON) go into
    "Local Folder/Extracted/<dated hierarchy>" instead of root-level folders.
  • After extraction, outputs are UPLOADED to the Box output_folder_id.
  • AI Assistant bases its lookups on the JSON files inside
    "Local Folder/Extracted/JSON File Extracts".

Screens (sidebar navigation):
  🏠 Home           — landing page with shortcut cards
  🔄 Sync Folder    — sync Box → Local Folder (manual + schedule status)
  📂 Scan Folder    — scan Local Folder for PDFs, show Pending/Completed status
  📊 Insights       — bar chart of extractions by period
  ⚙️  Extract Files  — extract PDFs from Local Folder, upload outputs to Box
  💬 AI Assistant   — chatbot grounded on Local Folder extracted JSON files

All network / file operations run on background threads.
UI updates posted back via self.after(0, …).

Log files → Log History / YYYY / MMM_YYYY / Week_NN / YYYY-MM-DD / <RefNo>_YYYYMMDD_HHMMSS.log
Tracking  → tracking_db.json  (per-file Pending / Completed state)
"""

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import importlib.util
import re as _re_ai

# ─────────────────────────────────────────────────────────────────────────────
# Module-level path constants
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.resolve()
CONFIG_PATH     = BASE_DIR / "config.json"
TRACKING_PATH   = BASE_DIR / "tracking_db.json"
LOG_HISTORY_DIR = BASE_DIR / "Log History"


# ─────────────────────────────────────────────────────────────────────────────
# Config loader helper (used outside frames too)
# ─────────────────────────────────────────────────────────────────────────────
def _read_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _local_folder() -> Path:
    """Return the resolved Local Folder path from config."""
    cfg  = _read_config()
    rel  = cfg.get("local", {}).get("local_folder", "Local Folder")
    path = Path(rel) if Path(rel).is_absolute() else BASE_DIR / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extracted_folder() -> Path:
    """Return the resolved Extracted sub-folder path from config."""
    cfg  = _read_config()
    rel  = cfg.get("local", {}).get("extracted_folder", "Local Folder/Extracted")
    path = Path(rel) if Path(rel).is_absolute() else BASE_DIR / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────
CLR_BG      = "#F0F4F8"
CLR_SIDEBAR = "#1F3864"
CLR_ACCENT  = "#2E75B6"
CLR_WHITE   = "#FFFFFF"
CLR_TEXT    = "#1F2328"
CLR_MUTED   = "#57606A"
CLR_GREEN   = "#22863A"
CLR_ORANGE  = "#D1622A"
CLR_PENDING = "#E6A817"
CLR_TEAL    = "#0D7377"   # used for Sync button

# ─────────────────────────────────────────────────────────────────────────────
# Font definitions
# ─────────────────────────────────────────────────────────────────────────────
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)


# ─────────────────────────────────────────────────────────────────────────────
# Tracking database helpers
# ─────────────────────────────────────────────────────────────────────────────
def load_tracking() -> dict:
    if TRACKING_PATH.exists():
        with open(TRACKING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}


def save_tracking(db: dict) -> None:
    with open(TRACKING_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Box client factory (Developer Token / OAuth2)
# ─────────────────────────────────────────────────────────────────────────────
def get_box_client():
    """
    Build a Box client from config.json using OAuth2 Developer Token.
    Returns (client, cfg).
    """
    from boxsdk import OAuth2, Client
    cfg  = _read_config()
    box  = cfg["box"]
    auth = OAuth2(
        client_id=box["client_id"],
        client_secret=box["client_secret"],
        access_token=box["access_token"],
    )
    return Client(auth), cfg


# ─────────────────────────────────────────────────────────────────────────────
# Folder hierarchy builder — dated output folders
# ─────────────────────────────────────────────────────────────────────────────
def build_extract_folder(base_dir: Path, when: datetime) -> Path:
    """
    Build (and create) the correct daily output folder:
      base_dir / YYYY / MMM_YYYY_Extracts / Week_NN / YYYY-MM-DD
    """
    year_folder   = base_dir / str(when.year)
    month_folder  = year_folder / f"{when.strftime('%b_%Y')}_Extracts"
    week_num      = when.isocalendar()[1]
    weekly_folder = month_folder / f"Week_{week_num:02d}"
    daily_folder  = weekly_folder / when.strftime("%Y-%m-%d")
    daily_folder.mkdir(parents=True, exist_ok=True)
    return daily_folder


# ─────────────────────────────────────────────────────────────────────────────
# Per-file extraction log writer
# ─────────────────────────────────────────────────────────────────────────────
def write_extraction_log(ref_number: str, when: datetime, content: str) -> Path:
    import re as _re
    year_folder  = LOG_HISTORY_DIR / str(when.year)
    month_folder = year_folder     / when.strftime("%b_%Y")
    week_num     = when.isocalendar()[1]
    week_folder  = month_folder    / f"Week_{week_num:02d}"
    day_folder   = week_folder     / when.strftime("%Y-%m-%d")
    day_folder.mkdir(parents=True, exist_ok=True)
    safe_ref  = _re.sub(r'[<>:"/\\|?*]', "_", ref_number).strip() or "UNKNOWN_REF"
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    log_path  = day_folder / f"{safe_ref}_{timestamp}.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return log_path


# ─────────────────────────────────────────────────────────────────────────────
# Box → Local Folder sync helper
# Downloads all PDFs from Box folder_id into local_folder.
# Returns (downloaded_count, skipped_count, errors).
# ─────────────────────────────────────────────────────────────────────────────
def sync_box_to_local(progress_cb=None) -> tuple[int, int, list[str]]:
    """
    Sync all PDF files from the configured Box folder_id into the Local Folder.

    progress_cb — optional callable(message: str) called for progress updates.
    Returns (downloaded, skipped, error_list).
    """
    cfg          = _read_config()
    box_cfg      = cfg["box"]
    folder_id    = box_cfg.get("folder_id", "0")
    local_folder = _local_folder()

    downloaded = 0
    skipped    = 0
    errors     = []

    def _cb(msg):
        if progress_cb:
            progress_cb(msg)

    _cb(f"Connecting to Box (folder {folder_id})…")

    try:
        from boxsdk import OAuth2, Client
        auth = OAuth2(
            client_id=box_cfg["client_id"],
            client_secret=box_cfg["client_secret"],
            access_token=box_cfg["access_token"],
        )
        client = Client(auth)
    except Exception as exc:
        errors.append(f"Box auth failed: {exc}")
        return 0, 0, errors

    def _sync_folder(fid: str, dest: Path, recurse: bool):
        nonlocal downloaded, skipped
        try:
            items = list(client.folder(fid).get_items(limit=1000))
        except Exception as exc:
            errors.append(f"Cannot list folder {fid}: {exc}")
            return
        for item in items:
            if item.type == "file" and item.name.lower().endswith(".pdf"):
                local_path = dest / item.name
                if local_path.exists():
                    skipped += 1
                    _cb(f"  Skip (exists): {item.name}")
                else:
                    try:
                        _cb(f"  Downloading: {item.name}")
                        data = client.file(item.id).content()
                        with open(local_path, "wb") as fh:
                            fh.write(data)
                        downloaded += 1
                        _cb(f"  ✅ Saved: {item.name}")
                    except Exception as exc:
                        errors.append(f"Download failed ({item.name}): {exc}")
            elif item.type == "folder" and recurse:
                sub_dest = dest / item.name
                sub_dest.mkdir(parents=True, exist_ok=True)
                _cb(f"  Entering subfolder: {item.name}")
                _sync_folder(item.id, sub_dest, recurse)

    search_sub = cfg.get("settings", {}).get("search_subfolders", True)
    _sync_folder(folder_id, local_folder, search_sub)
    _cb(f"Sync complete — {downloaded} downloaded, {skipped} skipped, {len(errors)} error(s).")
    return downloaded, skipped, errors


# ─────────────────────────────────────────────────────────────────────────────
# Box upload helper — upload a local file to a Box folder
# ─────────────────────────────────────────────────────────────────────────────
def upload_file_to_box(local_path: Path, box_folder_id: str,
                       client=None) -> str:
    """
    Upload *local_path* to Box folder *box_folder_id*.
    Creates subfolders on Box mirroring the path relative to Extracted root.
    Returns the Box file ID of the uploaded file.
    """
    if client is None:
        client, _ = get_box_client()

    # Upload directly to the target folder (flat, no mirror hierarchy for outputs)
    box_folder = client.folder(box_folder_id)
    # Check whether a file with the same name already exists (update vs upload)
    existing = {
        item.name: item.id
        for item in client.folder(box_folder_id).get_items(limit=1000)
        if item.type == "file"
    }
    if local_path.name in existing:
        # Update (new version) the existing file
        uploaded = client.file(existing[local_path.name]).update_contents(str(local_path))
    else:
        uploaded = box_folder.upload(str(local_path))
    return uploaded.id



# ══════════════════════════════════════════════════════════════════════════════
# Root application window
# ══════════════════════════════════════════════════════════════════════════════
class PDFExtractorAppV2(tk.Tk):
    """
    Main V2 application window.
    Sidebar navigation + stacked content frames.
    Auto-sync scheduler runs in the background if enabled in config.
    """

    def __init__(self):
        super().__init__()
        self.title("Background Check Report Automation V2")
        self.geometry("1150x720")
        self.minsize(950, 620)
        self.configure(bg=CLR_BG)
        self.resizable(True, True)

        self.db = load_tracking()

        self._build_layout()
        self._show_frame("home")
        self._start_auto_sync_scheduler()

    # ── Auto-sync scheduler ───────────────────────────────────────────────────
    def _start_auto_sync_scheduler(self):
        """
        If config.sync.auto_sync_enabled is true, kick off the first sync after
        10 seconds (to let the UI finish loading) and repeat every interval_minutes.
        """
        try:
            cfg       = _read_config()
            sync_cfg  = cfg.get("sync", {})
            enabled   = sync_cfg.get("auto_sync_enabled", False)
            interval  = int(sync_cfg.get("auto_sync_interval_minutes", 30))
        except Exception:
            return

        if not enabled:
            return

        def _run_sync():
            # Update the Sync frame's status label if it exists
            sf = self._frames.get("sync")
            if sf:
                self.after(0, lambda: sf._status_var.set(
                    f"⏰ Auto-sync running… (every {interval} min)"
                ))
            threading.Thread(target=self._auto_sync_worker,
                             args=(interval,), daemon=True).start()

        # Delay first auto-sync by 10 s so the window has time to render
        self.after(10_000, _run_sync)

    def _auto_sync_worker(self, interval_minutes: int):
        """Background worker that syncs and re-schedules itself."""
        try:
            sync_box_to_local()
            sf = self._frames.get("sync")
            now = datetime.now().strftime("%H:%M:%S")
            if sf:
                self.after(0, lambda: sf._status_var.set(
                    f"⏰ Last auto-sync: {now}  (next in {interval_minutes} min)"
                ))
        except Exception as exc:
            sf = self._frames.get("sync")
            if sf:
                self.after(0, lambda e=exc: sf._status_var.set(
                    f"⚠ Auto-sync error: {str(e)[:100]}"
                ))
        # Re-schedule
        self.after(interval_minutes * 60_000, lambda: threading.Thread(
            target=self._auto_sync_worker, args=(interval_minutes,), daemon=True
        ).start())

    # ── Layout construction ───────────────────────────────────────────────────
    def _build_layout(self):
        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = tk.Frame(self, bg=CLR_SIDEBAR, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="Background Check\nReport Automation V2",
            bg=CLR_SIDEBAR, fg=CLR_WHITE,
            font=("Segoe UI", 11, "bold"),
            pady=20,
        ).pack(fill="x")

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=12)

        nav_items = [
            ("  Home",           "home"),
            ("  Sync Folder",    "sync"),
            ("  Scan Folder",    "scan"),
            ("  Insights",       "insights"),
            ("  Extract Files",  "extract"),
            ("  AI Assistant",   "chat"),
        ]
        self._nav_btns = {}
        for label, key in nav_items:
            btn = tk.Button(
                sidebar,
                text=label,
                bg=CLR_SIDEBAR, fg=CLR_WHITE,
                font=FONT_LABEL,
                anchor="w", padx=16, pady=10,
                relief="flat", cursor="hand2",
                activebackground=CLR_ACCENT,
                activeforeground=CLR_WHITE,
                command=lambda k=key: self._show_frame(k),
            )
            btn.pack(fill="x")
            self._nav_btns[key] = btn

        tk.Label(
            sidebar, text="v2.0.0",
            bg=CLR_SIDEBAR, fg="#7090B0",
            font=FONT_SMALL,
        ).pack(side="bottom", pady=8)

        # ── Content area ──────────────────────────────────────────────────────
        self._content = tk.Frame(self, bg=CLR_BG)
        self._content.pack(side="left", fill="both", expand=True)

        self._frames = {}
        for key, cls in [
            ("home",     HomeFrame),
            ("sync",     SyncFrame),
            ("scan",     ScanFolderFrame),
            ("insights", InsightsFrame),
            ("extract",  ExtractFrame),
            ("chat",     ChatFrame),
        ]:
            frame = cls(self._content, self)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._frames[key] = frame

    def _show_frame(self, key: str):
        for k, btn in self._nav_btns.items():
            btn.config(bg=CLR_ACCENT if k == key else CLR_SIDEBAR)
        frame = self._frames[key]
        frame.lift()
        if hasattr(frame, "on_show"):
            self.after(0, frame.on_show)


# ══════════════════════════════════════════════════════════════════════════════
# Home Frame
# ══════════════════════════════════════════════════════════════════════════════
class HomeFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app = app

        tk.Label(
            self,
            text="Background Check Report Automation V2",
            bg=CLR_BG, fg=CLR_MUTED,
            font=("Segoe UI", 12),
        ).pack(pady=(40, 6))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=80, pady=20)

        # ── Row 1: Sync / Scan / Insights  ───────────────────────────────────
        row1 = tk.Frame(self, bg=CLR_BG)
        row1.pack()
        for icon, title, desc, key in [
            ("[SYNC]",    "Sync Folder",
             "Download PDFs from Box\ninto the Local Folder.",    "sync"),
            ("[SCAN]",    "Scan Folder",
             "Scan Local Folder for PDFs\nand view their status.", "scan"),
            ("[CHART]",   "Insights",
             "Charts and statistics on\nextraction progress.",    "insights"),
        ]:
            self._make_card(row1, icon, title, desc, key)

        # ── Row 2: Extract / AI Assistant ─────────────────────────────────────
        row2 = tk.Frame(self, bg=CLR_BG)
        row2.pack(pady=(0, 10))
        for icon, title, desc, key in [
            ("[EXTRACT]", "Extract Files",
             "Run extraction on Local Folder\nand upload outputs to Box.", "extract"),
            ("[AI]",      "AI Assistant",
             "Chat with WatsonX AI to query\nreports or trigger actions.", "chat"),
        ]:
            self._make_card(row2, icon, title, desc, key)

    def _make_card(self, parent, icon, title, desc, key):
        card = tk.Frame(
            parent, bg=CLR_WHITE, relief="flat", cursor="hand2",
            highlightbackground="#E5E7EB", highlightthickness=1,
        )
        card.pack(side="left", padx=12, pady=8, ipadx=16, ipady=14)
        nav = lambda e, k=key: self.app._show_frame(k)
        card.bind("<Button-1>", nav)

        # Coloured accent square instead of emoji
        _ICON_COLOURS = {
            "[SYNC]":    "#0D7377", "[SCAN]":    "#2E75B6",
            "[CHART]":   "#7C5CD8", "[EXTRACT]": "#22863A",
            "[AI]":      "#1F3864",
        }
        accent = _ICON_COLOURS.get(icon, CLR_ACCENT)
        lbl_icon = tk.Label(
            card, text=icon.strip("[]"),
            bg=accent, fg=CLR_WHITE,
            font=("Segoe UI", 9, "bold"),
            width=8, pady=6,
        )
        lbl_title = tk.Label(card, text=title, bg=CLR_WHITE, fg=CLR_TEXT,
                             font=FONT_BOLD, width=22)
        lbl_desc  = tk.Label(card, text=desc,  bg=CLR_WHITE, fg=CLR_MUTED,
                             font=FONT_SMALL, justify="center")
        lbl_icon.pack(pady=(0, 6))
        lbl_title.pack(pady=(0, 2))
        lbl_desc.pack()
        lbl_icon.bind("<Button-1>", nav)
        lbl_title.bind("<Button-1>", nav)
        lbl_desc.bind("<Button-1>", nav)


# ══════════════════════════════════════════════════════════════════════════════
# Sync Folder Frame — sync Box folder_id → Local Folder
# ══════════════════════════════════════════════════════════════════════════════
class SyncFrame(tk.Frame):
    """
    Allows the user to manually sync Box folder → Local Folder, and shows
    the current auto-sync schedule status.

    A scrollable log area shows real-time download progress.
    A "Sync Now" button triggers an immediate sync.
    Auto-sync schedule status is shown at the top.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app      = app
        self._syncing = False

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Sync Folder", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")
        self._sync_btn = tk.Button(
            hdr,
            text="  🔄  Sync Now  ",
            bg=CLR_TEAL, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat",
            cursor="hand2", padx=8, pady=6,
            command=self._sync_now,
        )
        self._sync_btn.pack(side="right")

        # ── Status / auto-sync label ──────────────────────────────────────────
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self._progress.pack(fill="x", padx=24, pady=(4, 4))

        # ── Log area ──────────────────────────────────────────────────────────
        tk.Label(self, text="Sync Log", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_BOLD).pack(anchor="w", padx=24, pady=(10, 2))
        log_frame = tk.Frame(self, bg=CLR_BG)
        log_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self._log_box = tk.Text(
            log_frame, bg=CLR_WHITE, fg=CLR_TEXT,
            font=FONT_MONO, relief="flat", state="disabled",
            highlightbackground="#E5E7EB", highlightthickness=1,
            padx=8, pady=6,
        )
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_box.yview)
        self._log_box.configure(yscrollcommand=sb.set)
        self._log_box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def on_show(self):
        pass

    def _log(self, msg: str):
        """Append a line to the sync log box. Must be called on the main thread."""
        self._log_box.config(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _sync_now(self):
        if self._syncing:
            return
        self._syncing = True
        self._sync_btn.config(state="disabled", text="  ⏳  Syncing…  ")
        self._progress.start(12)
        # Clear old log
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")
        self._status_var.set("Sync in progress…")
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _sync_worker(self):
        def _cb(msg):
            self.after(0, lambda m=msg: self._log(m))
        try:
            downloaded, skipped, errors = sync_box_to_local(progress_cb=_cb)
            summary = (
                f"✅ Sync complete — {downloaded} downloaded, "
                f"{skipped} already existed, {len(errors)} error(s)."
            )
            self.after(0, lambda s=summary: self._status_var.set(s))
            self.after(0, lambda s=summary: self._log(s))
            if errors:
                for e in errors:
                    self.after(0, lambda x=e: self._log(f"  ⚠ {x}"))
        except Exception as exc:
            msg = f"⚠ Sync failed: {str(exc)[:200]}"
            self.after(0, lambda m=msg: self._status_var.set(m))
            self.after(0, lambda m=msg: self._log(m))
        finally:
            self._syncing = False
            self.after(0, self._progress.stop)
            self.after(0, lambda: self._sync_btn.config(
                state="normal", text="  🔄  Sync Now  "
            ))


# ══════════════════════════════════════════════════════════════════════════════
# Scan Folder Frame — scans the LOCAL Folder (not Box)
# ══════════════════════════════════════════════════════════════════════════════
class ScanFolderFrame(tk.Frame):
    """
    Scans the Local Folder for PDF files and shows Pending / Completed status.
    Uses file path (relative to Local Folder) as the unique key instead of a
    Box file ID.  Each found PDF is reset to Pending (same logic as V1).
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app = app

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Scan Folder", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")
        self._scan_btn = tk.Button(
            hdr,
            text="  🔍  Scan Local Folder  ",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat",
            cursor="hand2", padx=8, pady=6,
            command=self._scan,
        )
        self._scan_btn.pack(side="right")

        # ── Summary bar ───────────────────────────────────────────────────────
        self._summary_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._summary_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(side="bottom", pady=6)

        # ── Table ─────────────────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg=CLR_BG)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        cols = ("File Name", "Relative Path", "Status", "Last Extracted", "Reference No.")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  selectmode="browse")
        widths = [260, 200, 90, 160, 160]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")
        self._tree.tag_configure("pending",   foreground=CLR_ORANGE)
        self._tree.tag_configure("completed", foreground=CLR_GREEN)

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        self._empty_label = tk.Label(
            table_frame,
            text="No PDF files found in Local Folder",
            bg=CLR_WHITE, fg=CLR_MUTED, font=("Segoe UI", 11),
            highlightbackground="#E5E7EB", highlightthickness=1,
        )

    def on_show(self):
        self._populate_from_db()

    def _populate_from_db(self):
        self._tree.delete(*self._tree.get_children())
        db      = load_tracking()
        files   = db.get("files", {})
        pending = completed = 0

        for fkey, info in files.items():
            status = info.get("status", "Pending")
            tag    = "pending" if status == "Pending" else "completed"
            if status == "Pending":
                pending += 1
            else:
                completed += 1
            self._tree.insert("", "end", values=(
                info.get("name",           ""),
                fkey,
                status,
                info.get("last_extracted", "--"),
                info.get("ref_number",     "--"),
            ), tags=(tag,))

        self._summary_var.set(
            f"Total: {len(files)}   |   ✅ Completed: {completed}   |   🕐 Pending: {pending}"
        )

        if len(files) == 0:
            self._tree.pack_forget()
            self._empty_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self._empty_label.place_forget()
            if not self._tree.winfo_ismapped():
                self._tree.pack(side="left", fill="both", expand=True)

    def _scan(self):
        self._scan_btn.config(state="disabled", text="  ⏳  Scanning…  ")
        self._status_var.set("Scanning Local Folder…")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        """
        Walk the Local Folder, find all .pdf files, and register them in
        tracking_db.json as Pending (preserving historical extraction info).
        Skips anything inside the Extracted sub-folder so extracts are not
        re-queued for extraction.
        """
        try:
            local_folder     = _local_folder()
            extracted_folder = _extracted_folder()
            db               = load_tracking()
            found            = 0

            for pdf_path in local_folder.rglob("*.pdf"):
                # Do not scan files that are already inside the Extracted folder
                try:
                    pdf_path.relative_to(extracted_folder)
                    continue   # skip — this PDF lives inside Extracted/
                except ValueError:
                    pass

                rel_key = str(pdf_path.relative_to(local_folder))
                existing = db.get("files", {}).get(rel_key, {})
                db["files"][rel_key] = {
                    "name":           pdf_path.name,
                    "status":         "Pending",
                    "last_extracted": existing.get("last_extracted"),
                    "ref_number":     existing.get("ref_number"),
                    "local_path":     str(pdf_path),
                }
                found += 1

            save_tracking(db)
            self.app.db = db

            self.after(0, self._populate_from_db)
            self.after(0, lambda: self._status_var.set(
                f"Scan complete — {found} PDF(s) found in Local Folder."
            ))
        except Exception as exc:
            msg = f"⚠ Scan failed: {str(exc)[:200]}"
            self.after(0, lambda m=msg: self._status_var.set(m))
        finally:
            self.after(0, lambda: self._scan_btn.config(
                state="normal", text="  🔍  Scan Local Folder  "
            ))


# ══════════════════════════════════════════════════════════════════════════════
# Insights Frame
# ══════════════════════════════════════════════════════════════════════════════
class InsightsFrame(tk.Frame):
    """Identical to V1 Insights — bar chart of Completed vs Pending by period."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app     = app
        self._filter = tk.StringVar(value="Month")

        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Extraction Insights", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")

        filter_frame = tk.Frame(hdr, bg=CLR_BG)
        filter_frame.pack(side="right")
        for opt in ("Day", "Week", "Month", "Year"):
            tk.Radiobutton(
                filter_frame, text=opt,
                variable=self._filter, value=opt,
                bg=CLR_BG, fg=CLR_TEXT, font=FONT_LABEL,
                activebackground=CLR_BG, selectcolor=CLR_BG,
                cursor="hand2", command=self._refresh,
            ).pack(side="left", padx=4)
        tk.Button(
            filter_frame, text="Refresh",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            command=self._refresh,
        ).pack(side="left", padx=(10, 0))

        self._cards_frame = tk.Frame(self, bg=CLR_BG)
        self._cards_frame.pack(fill="x", padx=24, pady=(0, 10))

        self._canvas = tk.Canvas(
            self, bg=CLR_WHITE,
            highlightbackground="#E5E7EB", highlightthickness=1,
        )
        self._canvas.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self._canvas.bind("<Configure>", lambda e: self._draw_chart())
        self._chart_data: dict = {}

    def on_show(self):
        self._refresh()

    def _refresh(self):
        db     = load_tracking()
        files  = db.get("files", {})
        period = self._filter.get()
        now    = datetime.now()
        buckets: dict[str, dict] = defaultdict(lambda: {"Pending": 0, "Completed": 0})
        for info in files.values():
            status = info.get("status", "Pending")
            ts     = info.get("last_extracted")
            if ts:
                try:    dt = datetime.fromisoformat(ts)
                except: dt = now
            else:
                dt = now
            if period == "Day":       key = dt.strftime("%Y-%m-%d")
            elif period == "Week":
                iso = dt.isocalendar(); key = f"{iso[0]}-W{iso[1]:02d}"
            elif period == "Month":   key = dt.strftime("%b %Y")
            else:                     key = str(dt.year)
            buckets[key][status] += 1
        self._chart_data = dict(sorted(buckets.items()))

        for w in self._cards_frame.winfo_children():
            w.destroy()
        total     = len(files)
        completed = sum(1 for i in files.values() if i.get("status") == "Completed")
        pending   = total - completed
        for label, val, colour in [
            ("Total Files", total, CLR_ACCENT),
            ("✅ Completed", completed, CLR_GREEN),
            ("🕐 Pending",   pending,  CLR_PENDING),
        ]:
            card = tk.Frame(self._cards_frame, bg=colour, padx=20, pady=12)
            card.pack(side="left", padx=6, ipadx=6)
            tk.Label(card, text=str(val),  bg=colour, fg=CLR_WHITE,
                     font=("Segoe UI", 18, "bold")).pack()
            tk.Label(card, text=label,     bg=colour, fg=CLR_WHITE,
                     font=FONT_SMALL).pack()
        self._draw_chart()

    def _draw_chart(self):
        c = self._canvas
        c.delete("all")
        if not self._chart_data:
            c.create_text(c.winfo_width()//2, c.winfo_height()//2,
                          text="No data — scan folder first.", fill=CLR_MUTED, font=FONT_LABEL)
            return
        W = c.winfo_width(); H = c.winfo_height()
        if W < 10 or H < 10: return
        pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 60
        keys    = list(self._chart_data.keys())
        n       = len(keys)
        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b
        max_v   = max((v["Pending"]+v["Completed"] for v in self._chart_data.values()), default=1) or 1
        bar_w   = max(6, chart_w // (n*2+1))
        gap     = bar_w // 2
        c.create_line(pad_l, pad_t, pad_l, H-pad_b, fill=CLR_MUTED, width=1)
        c.create_line(pad_l, H-pad_b, W-pad_r, H-pad_b, fill=CLR_MUTED, width=1)
        for i in range(5):
            y_val = max_v*i/4; y_px = H-pad_b-int(chart_h*i/4)
            c.create_line(pad_l, y_px, W-pad_r, y_px, fill="#E5E7EB", dash=(2,4))
            c.create_text(pad_l-6, y_px, text=str(int(y_val)), anchor="e", fill=CLR_MUTED, font=FONT_SMALL)
        slot = chart_w / n
        for idx, key in enumerate(keys):
            data   = self._chart_data[key]
            x_base = pad_l + int(idx*slot+slot/2) - bar_w - gap//2
            for j, (status, colour) in enumerate([("Completed", CLR_GREEN), ("Pending", CLR_PENDING)]):
                val = data[status]
                bh  = int(chart_h*val/max_v) if max_v else 0
                x0  = x_base + j*(bar_w+gap); y0 = H-pad_b-bh
                x1  = x0+bar_w;               y1 = H-pad_b
                c.create_rectangle(x0, y0, x1, y1, fill=colour, outline="", tags="bar")
                if bh > 12:
                    c.create_text((x0+x1)//2, y0+6, text=str(val), fill=CLR_WHITE, font=("Segoe UI",7,"bold"))
            lbl = key if len(key)<=10 else key[-7:]
            c.create_text(pad_l+int(idx*slot+slot/2), H-pad_b+14,
                          text=lbl, fill=CLR_TEXT, font=FONT_SMALL)
        for i, (label, colour) in enumerate([("Completed", CLR_GREEN), ("Pending", CLR_PENDING)]):
            lx = W-160+i*80
            c.create_rectangle(lx, pad_t, lx+12, pad_t+12, fill=colour, outline="")
            c.create_text(lx+16, pad_t+6, text=label, anchor="w", fill=CLR_TEXT, font=FONT_SMALL)



# ══════════════════════════════════════════════════════════════════════════════
# Extract Frame — read PDFs from Local Folder, save to Extracted/, upload to Box
# ══════════════════════════════════════════════════════════════════════════════
class ExtractFrame(tk.Frame):
    """
    Extraction pipeline — V2 edition.

    Changes from V1:
      • Reads PDFs from the Local Folder (not from Box).
      • Saves all outputs (Word / Excel / JSON) inside
        Local Folder/Extracted/<dated hierarchy>/<ref_number>/.
      • After successful extraction, uploads the three output files to the
        Box output_folder_id configured in config.json.
      • Does NOT move the source PDF to an archive on Box — source stays in
        Local Folder so the user can re-extract if needed.
      • Marks each processed file Completed in tracking_db.json.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app      = app
        self._running = False

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Extract Files", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")
        self._btn = tk.Button(
            hdr,
            text="  ▶  Start Extraction  ",
            bg=CLR_GREEN, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat",
            cursor="hand2", padx=8, pady=6,
            command=self._start_extraction,
        )
        self._btn.pack(side="right")

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self._progress.pack(fill="x", padx=24, pady=(0, 6))

        # ── Status label ──────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self._status_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24)

        # ── Scrollable results panel ──────────────────────────────────────────
        tk.Label(self, text="Results", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_BOLD).pack(anchor="w", padx=24, pady=(20, 4))
        container = tk.Frame(self, bg=CLR_BG)
        container.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self._canvas = tk.Canvas(container, bg=CLR_BG, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._results_frame = tk.Frame(self._canvas, bg=CLR_BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._results_frame, anchor="nw"
        )
        self._results_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width),
        )

    def _log_write(self, msg: str):
        pass   # silent stub — logs go to disk

    def _add_result_card(self, fname, ref, status, word, excel, json_, upload_status=""):
        ok     = (status == "ok")
        colour = CLR_GREEN if ok else CLR_ORANGE
        card = tk.Frame(
            self._results_frame, bg=CLR_WHITE,
            highlightbackground="#E5E7EB", highlightthickness=1,
        )
        card.pack(fill="x", pady=4, ipady=8, ipadx=10)
        top = tk.Frame(card, bg=CLR_WHITE)
        top.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(top, text=fname, bg=CLR_WHITE, fg=CLR_TEXT,
                 font=FONT_BOLD, anchor="w").pack(side="left")
        badge_text = "✅  Completed" if ok else "❌  Failed"
        tk.Label(top, text=badge_text, bg=colour, fg=CLR_WHITE,
                 font=FONT_SMALL, padx=8, pady=2).pack(side="right")
        if ok:
            tk.Label(card, text=f"Reference:  {ref}", bg=CLR_WHITE,
                     fg=CLR_MUTED, font=FONT_SMALL, anchor="w").pack(
                         fill="x", padx=10, pady=(0, 2))
            for icon, path in [
                ("📄 Word",  word),
                ("📊 Excel", excel),
                ("🗂 JSON",  json_),
            ]:
                tk.Label(
                    card, text=f"{icon}:  {path}",
                    bg=CLR_WHITE, fg=CLR_MUTED, font=FONT_SMALL,
                    anchor="w", wraplength=700, justify="left",
                ).pack(fill="x", padx=10)
            if upload_status:
                tk.Label(
                    card, text=f"☁️ Box Upload: {upload_status}",
                    bg=CLR_WHITE, fg=CLR_MUTED, font=FONT_SMALL,
                    anchor="w",
                ).pack(fill="x", padx=10)
        else:
            tk.Label(
                card, text=ref,
                bg=CLR_WHITE, fg="#C0392B",
                font=FONT_SMALL, anchor="w",
                wraplength=700, justify="left",
            ).pack(fill="x", padx=10, pady=(0, 4))

    def _start_extraction(self):
        if self._running:
            return
        self._running = True
        self._btn.config(state="disabled", text="  ⏳  Extracting…  ")
        self._progress.start(12)
        for w in self._results_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self._run_extraction, daemon=True).start()

    def _run_extraction(self):
        try:
            self._do_extraction()
        except Exception as exc:
            self.after(0, lambda e=exc: self._status_var.set(f"Error: {e}"))
        finally:
            self._running = False
            self.after(0, self._extraction_done)

    def _extraction_done(self):
        self._progress.stop()
        self._btn.config(state="normal", text="  ▶  Start Extraction  ")

    def _do_extraction(self):
        """
        V2 extraction pipeline (background thread):
          1. Dynamically load pdf_text_extractor.py
          2. Read config — get pdf_password, output_folder_id
          3. Iterate Pending files from tracking_db.json
          4. Open local PDF file
          5. Decrypt + extract text
          6. Parse into structured dict
          7. Export Word / Excel / JSON to Extracted/ dated hierarchy
          8. Upload outputs to Box output_folder_id
          9. Mark file Completed in tracking DB
         10. Write per-file .log
         11. Add result card to UI
        """
        spec = importlib.util.spec_from_file_location(
            "pdf_text_extractor", BASE_DIR / "pdf_text_extractor.py"
        )
        extractor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extractor)

        self.after(0, lambda: self._status_var.set("Loading extractor module…"))

        cfg              = _read_config()
        password         = cfg.get("pdf_password", "")
        output_folder_id = cfg.get("box", {}).get("output_folder_id", "")
        extracted_root   = _extracted_folder()

        # Sub-directories inside Extracted/
        word_root = extracted_root / "Word Extracts"
        csv_root  = extracted_root / "CSV Extracts"
        json_root = extracted_root / "JSON File Extracts"
        for d in (word_root, csv_root, json_root):
            d.mkdir(parents=True, exist_ok=True)

        # ── Load tracking DB and collect Pending files ────────────────────────
        db      = load_tracking()
        pending = {
            k: v for k, v in db.get("files", {}).items()
            if v.get("status", "Pending") == "Pending"
        }

        if not pending:
            self.after(0, lambda: self._status_var.set(
                "No Pending files found. Scan the folder first."
            ))
            return

        # Connect to Box only if upload is configured
        box_client = None
        if output_folder_id and not output_folder_id.startswith("YOUR_"):
            try:
                self.after(0, lambda: self._status_var.set("Connecting to Box for upload…"))
                box_client, _ = get_box_client()
            except Exception as exc:
                self.after(0, lambda e=exc: self._status_var.set(
                    f"⚠ Box connection failed (uploads disabled): {e}"
                ))

        now = datetime.now()

        for rel_key, info in pending.items():
            fname      = info.get("name", rel_key)
            local_path = Path(info.get("local_path", ""))

            if not local_path.exists():
                # Try reconstructing path from Local Folder
                local_path = _local_folder() / rel_key

            self.after(0, lambda n=fname: self._status_var.set(f"Processing: {n}"))

            try:
                # Step 1 — Read PDF bytes from disk
                with open(local_path, "rb") as fh:
                    pdf_bytes = fh.read()

                # Step 2 — Decrypt + extract text
                doc   = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
                pages = extractor.extract_text_by_page(doc)
                doc.close()

                # Step 3 — Parse
                structured = extractor.build_structured_json(fname, pages)
                ref_number = (
                    structured.get("report_summary", {})
                               .get("case_reference", "").strip()
                    or Path(fname).stem
                )

                # Step 4 — Export to Extracted/ dated hierarchy
                daily_word = build_extract_folder(word_root, now)
                daily_csv  = build_extract_folder(csv_root,  now)
                daily_json = build_extract_folder(json_root, now)

                # Temporarily redirect extractor's output-dir constants
                orig_word = extractor.WORD_OUT_DIR
                orig_csv  = extractor.CSV_OUT_DIR
                orig_json = extractor.JSON_OUT_DIR
                extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = (
                    daily_word, daily_csv, daily_json
                )
                try:
                    word_path = extractor.export_to_word(fname, structured, ref_number, False)
                    csv_path  = extractor.export_to_csv( fname, structured, ref_number, False)
                    json_path = extractor.export_to_json(fname, structured, ref_number, False)
                finally:
                    extractor.WORD_OUT_DIR = orig_word
                    extractor.CSV_OUT_DIR  = orig_csv
                    extractor.JSON_OUT_DIR = orig_json

                # Step 5 — Upload to Box output_folder_id
                upload_status = ""
                if box_client and output_folder_id:
                    try:
                        for out_path in (word_path, csv_path, json_path):
                            upload_file_to_box(out_path, output_folder_id, box_client)
                        upload_status = f"Uploaded 3 file(s) to Box folder {output_folder_id}"
                    except Exception as up_exc:
                        upload_status = f"Upload failed: {str(up_exc)[:120]}"
                else:
                    upload_status = "Box upload not configured (set output_folder_id in config.json)"

                # Step 6 — Mark Completed in tracking DB
                db["files"][rel_key].update({
                    "name":           fname,
                    "status":         "Completed",
                    "last_extracted": now.isoformat(timespec="seconds"),
                    "ref_number":     ref_number,
                })

                # Step 7 — Write extraction log
                log_lines = [
                    "Background Check Report Automation V2 — Extraction Log",
                    "=" * 60,
                    f"File       : {fname}",
                    f"Reference  : {ref_number}",
                    f"Started    : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Completed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Status     : Completed",
                    "",
                    "Outputs",
                    "-" * 40,
                    f"Word  : {word_path}",
                    f"Excel : {csv_path}",
                    f"JSON  : {json_path}",
                    "",
                    f"Box Upload : {upload_status}",
                ]
                write_extraction_log(ref_number, now, "\n".join(log_lines))

                # Step 8 — Add result card
                self.after(0, lambda f=fname, r=ref_number,
                                      w=str(word_path.relative_to(BASE_DIR)),
                                      x=str(csv_path.relative_to(BASE_DIR)),
                                      j=str(json_path.relative_to(BASE_DIR)),
                                      u=upload_status:
                    self._add_result_card(f, r, "ok", w, x, j, u)
                )

            except Exception as exc:
                db["files"][rel_key].setdefault("status", "Pending")
                ref_fallback = Path(fname).stem
                log_lines = [
                    "Background Check Report Automation V2 — Extraction Log",
                    "=" * 60,
                    f"File    : {fname}",
                    f"Started : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Failed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Status  : FAILED", "", "Error", "-" * 40, str(exc),
                ]
                write_extraction_log(ref_fallback, now, "\n".join(log_lines))
                self.after(0, lambda f=fname, e=str(exc):
                    self._add_result_card(f, e, "error", "", "", "")
                )

        save_tracking(db)
        self.app.db = db
        self.after(0, lambda: self._status_var.set("Extraction complete."))


# ══════════════════════════════════════════════════════════════════════════════
# AI Assistant helpers — grounded on Local Folder / Extracted JSON files
# (Logic mirrors V1 exactly; only the JSON source directory changes.)
# ══════════════════════════════════════════════════════════════════════════════

# JSON source: Extracted/JSON File Extracts  (populated by extraction pipeline)
def _ai_json_dir() -> Path:
    return _extracted_folder() / "JSON File Extracts"


_STATUS_EMOJI = {
    "cleared": "✅", "verified": "✅", "pass": "✅", "passed": "✅", "clear": "✅",
    "failed": "❌", "fail": "❌", "unverified": "❌", "adverse": "❌",
    "--": "⬜", "": "⬜",
}

def _status_icon(val: str) -> str:
    v = (val or "").strip().lower()
    for key, icon in _STATUS_EMOJI.items():
        if key and key in v:
            return icon
    return "🔵"


def skill_lookup_report(query: str) -> str:
    """Search extracted JSON reports in Local Folder by subject name or case ref."""
    if not query.strip():
        return "Please provide a name or reference number to search for."

    q_lower    = query.strip().lower()
    best_by_ref: dict = {}
    json_dir   = _ai_json_dir()

    def _ingest(report: dict):
        s    = report.get("report_summary", {})
        name = s.get("subject_name", "").lower()
        ref  = s.get("case_reference", "").lower()
        if q_lower not in name and q_lower not in ref:
            return
        existing = best_by_ref.get(ref)
        if existing is None:
            best_by_ref[ref] = report
        else:
            if report.get("extracted_at", "") > existing.get("extracted_at", ""):
                best_by_ref[ref] = report

    if json_dir.exists():
        for jp in json_dir.rglob("*.json"):
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    _ingest(json.load(fh))
            except Exception:
                continue

    if not best_by_ref:
        return f"No reports found matching '{query}'."

    matches = list(best_by_ref.values())

    OTHER_CHECK_ORDER = [
        "Adverse Media Check", "Global Sanctions", "Bankruptcy Check",
        "Financial/Credit Check", "Directorship Check", "Civil Litigation Check",
        "Professional License Qualification", "Social Media Screening",
    ]

    blocks = []
    for r in matches[:5]:
        s        = r.get("report_summary", {})
        subject  = s.get("subject_name", "--")
        ref_num  = s.get("case_reference", "--")
        delivery = s.get("delivery_date", "--")
        received = s.get("case_received", "")
        package  = s.get("package", "")
        overall  = s.get("overall_status", "--")

        lines = []
        lines.append(f"Subject: {subject} | Ref: {ref_num} | Delivery: {delivery}")
        if received and received.strip():
            lines.append(f"Case Received: {received}")
        if package and package.strip():
            lines.append(f"Package: {package}")
        lines.append(f"Overall Status: {_status_icon(overall)} {overall}")
        lines.append("")

        emp_checks = r.get("employment_checks", [])
        if emp_checks:
            lines.append("── Employment Verification ──")
            for ec in emp_checks:
                emp_status = ec.get("verification_status", "--")
                lines.append(
                    f"  {_status_icon(emp_status)} Employment {ec.get('check_number','?')}: "
                    f"{ec.get('employer_name','--')} — {emp_status}"
                )
                for label, key in [
                    ("Position","position_title"), ("Address","company_address"),
                    ("Dates","dates_of_employment"), ("Employment Status","status_of_employment"),
                    ("Reason for Exit","reason_for_exit"), ("Eligible for Rehire","eligible_for_rehire"),
                    ("Respondent","respondents_name"), ("Respondent Title","respondents_title"),
                    ("Contact","contact_details"), ("Verification Date","verification_date"),
                    ("Result","result"), ("Notes","notes"),
                ]:
                    val = ec.get(key, "")
                    if val and str(val).strip():
                        lines.append(f"    {label}: {val}")
            lines.append("")

        ref_checks = r.get("professional_reference_checks", [])
        if ref_checks:
            lines.append("── Professional References ──")
            for pr in ref_checks:
                ref_status = pr.get("verification_status", "--")
                lines.append(
                    f"  {_status_icon(ref_status)} Reference {pr.get('check_number','?')}: "
                    f"{pr.get('referee_name','--')} — {ref_status}"
                )
                for label, key in [
                    ("Result","result"), ("Verifier Name","verifiers_name"),
                    ("Verifier Contact","verifiers_contact"), ("Notes","notes"),
                ]:
                    val = pr.get(key, "")
                    if val and str(val).strip() and str(val).strip() != "-":
                        lines.append(f"    {label}: {val}")
                for qa in pr.get("qa", []):
                    answer = qa.get("answer","").strip(); question = qa.get("question","").strip()
                    if answer and question:
                        lines.append(f"    Q: {question}"); lines.append(f"    A: {answer}")
            lines.append("")

        other_map = {
            oc.get("check_name","").strip().lower(): oc
            for oc in r.get("other_checks", [])
        }
        lines.append("── Database Checks ──")
        for check_name in OTHER_CHECK_ORDER:
            oc       = next((v for k, v in other_map.items() if k == check_name.lower()), {})
            status   = oc.get("status", "--") if oc else "--"
            chk_icon = _status_icon(status)
            lines.append(f"  {chk_icon} {check_name}: {status}")
            for field_key in ("result", "source"):
                fv = oc.get(field_key, "") if oc else ""
                if fv and str(fv).strip():
                    lines.append(f"    {field_key.capitalize()}: {fv}")

        blocks.append("\n".join(lines))

    header = ""
    if len(matches) > 1:
        header = (
            f"Found {len(matches)} record(s) matching '{query}':\n"
            + "\n".join(
                f"  • {r.get('report_summary',{}).get('subject_name','--')} "
                f"— Ref: {r.get('report_summary',{}).get('case_reference','--')}"
                for r in matches[:5]
            ) + "\n\n"
        )
    return header + "\n\n".join(blocks)


def get_log_history(period: str = "day") -> str:
    """Return a plain-text summary of extraction logs for the given period."""
    today  = datetime.now().date()
    cutoff = {
        "day":   today,
        "week":  today - timedelta(days=today.weekday()),
        "month": today.replace(day=1),
        "year":  today.replace(month=1, day=1),
    }.get(period.lower(), today)
    if not LOG_HISTORY_DIR.exists():
        return "No log history found."
    log_files = []
    for log_path in LOG_HISTORY_DIR.rglob("*.log"):
        parts    = log_path.parts
        date_str = parts[-2] if len(parts) >= 2 else ""
        try:    log_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except: log_date = today
        if log_date >= cutoff:
            log_files.append((log_date, log_path))
    if not log_files:
        return f"No log entries found for the selected period ({period})."
    log_files.sort(key=lambda x: x[0], reverse=True)
    lines = [f"=== LOG HISTORY ({period.upper()}) — {len(log_files)} file(s) ==="]
    for log_date, log_path in log_files:
        lines.append(f"\n[{log_date}]  {log_path.name}")
        try:
            with open(log_path, "r", encoding="utf-8") as fh:
                content_lines = fh.read().splitlines()
            lines.append("\n".join(f"  {l}" for l in content_lines[:10]))
            if len(content_lines) > 10:
                lines.append(f"  … ({len(content_lines) - 10} more lines)")
        except Exception:
            lines.append("  (could not read log file)")
    lines.append("\n=== END LOG HISTORY ===")
    return "\n".join(lines)


def trigger_extraction_for_chat() -> str:
    """Run the full extraction pipeline synchronously and return a text summary."""
    import importlib.util as _ilu
    spec      = _ilu.spec_from_file_location("pdf_text_extractor", BASE_DIR / "pdf_text_extractor.py")
    extractor = _ilu.module_from_spec(spec)
    spec.loader.exec_module(extractor)

    cfg              = _read_config()
    password         = cfg.get("pdf_password", "")
    output_folder_id = cfg.get("box", {}).get("output_folder_id", "")
    extracted_root   = _extracted_folder()
    word_root        = extracted_root / "Word Extracts"
    csv_root         = extracted_root / "CSV Extracts"
    json_root        = extracted_root / "JSON File Extracts"
    for d in (word_root, csv_root, json_root):
        d.mkdir(parents=True, exist_ok=True)

    db      = load_tracking()
    pending = {k: v for k, v in db.get("files", {}).items()
               if v.get("status", "Pending") == "Pending"}

    if not pending:
        return "No Pending PDF files found in Local Folder. Run Scan Folder first."

    box_client = None
    if output_folder_id and not output_folder_id.startswith("YOUR_"):
        try:
            box_client, _ = get_box_client()
        except Exception:
            pass

    now     = datetime.now()
    results = [f"Extraction started at {now.strftime('%Y-%m-%d %H:%M:%S')}",
               f"Files found: {len(pending)}", ""]

    for rel_key, info in pending.items():
        fname      = info.get("name", rel_key)
        local_path = Path(info.get("local_path", ""))
        if not local_path.exists():
            local_path = _local_folder() / rel_key
        try:
            with open(local_path, "rb") as fh:
                pdf_bytes = fh.read()
            doc        = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
            pages      = extractor.extract_text_by_page(doc)
            doc.close()
            structured = extractor.build_structured_json(fname, pages)
            ref_number = (
                structured.get("report_summary", {}).get("case_reference", "").strip()
                or Path(fname).stem
            )
            daily_word = build_extract_folder(word_root, now)
            daily_csv  = build_extract_folder(csv_root,  now)
            daily_json = build_extract_folder(json_root, now)
            orig = extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR
            extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = (
                daily_word, daily_csv, daily_json
            )
            try:
                word_path = extractor.export_to_word(fname, structured, ref_number, False)
                csv_path  = extractor.export_to_csv( fname, structured, ref_number, False)
                json_path = extractor.export_to_json(fname, structured, ref_number, False)
            finally:
                extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = orig

            upload_status = ""
            if box_client and output_folder_id:
                try:
                    for op in (word_path, csv_path, json_path):
                        upload_file_to_box(op, output_folder_id, box_client)
                    upload_status = f"Uploaded to Box folder {output_folder_id}"
                except Exception as ue:
                    upload_status = f"Upload failed: {str(ue)[:80]}"

            db["files"][rel_key].update({
                "name": fname, "status": "Completed",
                "last_extracted": now.isoformat(timespec="seconds"),
                "ref_number": ref_number,
            })
            log_lines = [
                "Background Check Report Automation V2 — Extraction Log",
                "=" * 60, f"File: {fname}", f"Reference: {ref_number}",
                f"Started: {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "", "Outputs", "-" * 40,
                f"Word  : {word_path}", f"Excel : {csv_path}", f"JSON  : {json_path}",
                f"Box Upload: {upload_status}",
            ]
            log_path = write_extraction_log(ref_number, now, "\n".join(log_lines))
            results.append(
                f"✅  {fname}\n"
                f"   Reference : {ref_number}\n"
                f"   Word      : {word_path.relative_to(BASE_DIR)}\n"
                f"   Excel     : {csv_path.relative_to(BASE_DIR)}\n"
                f"   JSON      : {json_path.relative_to(BASE_DIR)}\n"
                f"   Upload    : {upload_status}\n"
                f"   Log       : {log_path.relative_to(BASE_DIR)}"
            )
        except Exception as exc:
            ref_fallback = Path(fname).stem
            db["files"][rel_key].setdefault("status", "Pending")
            log_lines = [
                "Background Check Report Automation V2 — Extraction Log",
                "=" * 60, f"File: {fname}",
                f"Started: {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Failed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status: FAILED", "", "Error", "-" * 40, str(exc),
            ]
            log_path = write_extraction_log(ref_fallback, now, "\n".join(log_lines))
            results.append(f"❌  {fname}\n   Error : {str(exc)[:300]}")

    save_tracking(db)
    completed = sum(1 for r in results if r.startswith("✅"))
    failed    = sum(1 for r in results if r.startswith("❌"))
    results.insert(2, f"Completed: {completed}  |  Failed: {failed}\n")
    return "\n".join(results)


# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers (identical to V1)
# ─────────────────────────────────────────────────────────────────────────────
_AI_SYSTEM_PROMPT = (
    "You are Detective Conan, an AI assistant for the Background Check Report Automation system. "
    "You help HR staff manage background check reports processed through IBM Box.\n\n"
    "You can help with:\n"
    "- Answering questions about background check reports (employment, criminal, identity checks)\n"
    "- Explaining file status, extraction results, and logs\n"
    "- Guiding users to use commands: 'scan folder', 'run extraction', 'file status', "
    "'look up [name]', 'logs this week'\n\n"
    "CRITICAL RULES — you MUST follow these without exception:\n"
    "1. YOUR ONLY SOURCE OF TRUTH IS THE EXTRACTED RECORDS. Every factual answer you "
    "give about a person, report, employer, check result, date, or any other data point "
    "MUST come exclusively from records retrieved by the 'look up' skill and provided to "
    "you in this conversation. Your training knowledge is NOT a valid source for any "
    "background check information.\n"
    "2. NEVER invent, fabricate, or hallucinate any background check report data. "
    "This includes subject names, employers, employment dates, criminal records, "
    "education history, identity verification results, or any other report details.\n"
    "3. If a user asks about a report and no extracted record data has been provided to "
    "you in this conversation, reply ONLY with: "
    "\"I can only answer from our extracted records. Please use 'look up [name or reference]' "
    "to retrieve the report first.\"\n"
    "4. You may only describe data that was explicitly present in a look-up result "
    "delivered in this conversation. Do not expand, embellish, infer, or add any "
    "details not present verbatim in that data.\n"
    "5. Never produce a formatted 'CONFIDENTIAL BACKGROUND CHECK REPORT' or any "
    "document that resembles an official report unless the exact data was given to you "
    "by the system in this conversation.\n"
    "6. If a user asks ANY question whose answer would require data not present in the "
    "extracted records provided in this conversation, respond with: "
    "\"I don't have that information in the extracted records. "
    "Please use 'look up [name or reference]' to search our records.\"\n"
    "7. NEVER simulate, role-play, or imitate a lookup process. Do NOT produce text like "
    "'Looking up X...', 'Found X match', 'Found 1 match', 'Searching for...', or any "
    "UI-style progress message. You are not a search engine and must never pretend to be one. "
    "The lookup system is handled exclusively by the server-side skill — it is NOT your job.\n"
    "8. NEVER produce any personal data (names, employers, dates, check results, "
    "reference numbers) about any individual that was not delivered to you verbatim "
    "by the system in this conversation. If you do not have an EXTRACTED RECORD anchor "
    "in your context, you have zero data about any person — treat all persons as unknown.\n\n"
    "Be professional, concise, and helpful. Never make hiring recommendations. "
    "If asked about something unrelated to background checks or the system, "
    "politely redirect to your core purpose."
)


def _load_ai_config() -> dict:
    return _read_config()


def granite_chat(history: list[dict], user_message: str) -> str:
    import urllib.request, urllib.error, ssl
    cfg         = _load_ai_config()
    wx          = cfg.get("watsonx", {})
    api_key     = wx.get("api_key", "")
    project_id  = wx.get("project_id", "")
    service_url = wx.get("url", "https://us-south.ml.cloud.ibm.com").rstrip("/")
    model       = wx.get("model_id", "ibm/granite-3-8b-instruct")
    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError("watsonx.ai api_key not configured in config.json")
    if not project_id or project_id.startswith("YOUR_") or project_id.startswith("ApiKey-"):
        raise ValueError("watsonx.ai project_id not configured in config.json")
    token_req = urllib.request.Request(
        "https://iam.cloud.ibm.com/identity/token",
        data=f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(token_req, timeout=15, context=ctx) as resp:
        iam_token = json.loads(resp.read())["access_token"]
    messages = [{"role": "system", "content": _AI_SYSTEM_PROMPT}]
    for turn in (history[-10:] if history else []):
        messages.append({"role": turn.get("role","user"), "content": turn.get("content","")})
    messages.append({"role": "user", "content": user_message})
    url     = f"{service_url}/ml/v1/text/chat?version=2024-05-01"
    payload = json.dumps({
        "model_id": model, "project_id": project_id,
        "messages": messages, "parameters": {"max_new_tokens": 2048, "temperature": 0.7},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json", "Accept": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"watsonx.ai error {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    choices = result.get("choices", [])
    reply   = choices[0].get("message",{}).get("content","").strip() if choices else ""
    return reply if reply else "(No response from Granite)"


def groq_chat(history: list[dict], user_message: str) -> str:
    import urllib.request, urllib.error, ssl
    cfg     = _load_ai_config()
    gc      = cfg.get("groq", {})
    api_key = gc.get("api_key", "")
    model   = gc.get("model", "llama-3.3-70b-versatile")
    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError("Groq API key not configured in config.json")
    messages = [{"role": "system", "content": _AI_SYSTEM_PROMPT}]
    for turn in (history[-10:] if history else []):
        messages.append({"role": turn.get("role","user"), "content": turn.get("content","")})
    messages.append({"role": "user", "content": user_message})
    payload = json.dumps({
        "model": model, "messages": messages,
        "max_tokens": 4096, "temperature": 0.7,
    }).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Groq API error {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    reply = result["choices"][0]["message"]["content"].strip()
    return reply if reply else "(No response from Groq)"


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination guard (identical to V1)
# ─────────────────────────────────────────────────────────────────────────────
_HALLUCINATION_PATTERNS = [
    r"looking\s+up\s+['\"]?.+['\"]?[\s\.]*\.\.",
    r"looking\s+up\s+['\"][\w\s]+['\"]",
    r"found\s+\d+\s+match",
    r"searching\s+for\s+.+\.{2,}",
    r"i\s+found\s+(a\s+)?match",
    r"^name\s*:\s+[A-Z][a-z]",
    r"report\s+type\s*:\s+\w",
    r"date\s*:\s+\d{4}-\d{2}-\d{2}",
    r"confidential\s+background\s+check\s+report",
    r"detailed\s+report\s*:",
    r"employment\s+history\s*:",
    r"identity\s+verification\s*:",
    r"bachelor.{0,15}degree",
    r"abc\s+corporation",
    r"def\s+company",
    r"would\s+you\s+like\s+to\s+(view|see)\s+the\s+full\s+report",
    r"criminal\s+records?\s*:\s*no\s+criminal",
    r"no\s+felony\s+or\s+misdemeanor",
    r"government.{0,10}issued\s+id\s+verified",
    r"\u00a7[A-Z_]+\u00a7",
]
_HALLUCINATION_RE = _re_ai.compile(
    "|".join(_HALLUCINATION_PATTERNS), _re_ai.IGNORECASE | _re_ai.MULTILINE
)


def _is_hallucinated_reply(reply: str) -> bool:
    return bool(_HALLUCINATION_RE.search(reply))


def _sanitize_history(history: list[dict]) -> list[dict]:
    clean = []
    for turn in history:
        if turn.get("role") == "assistant" and _is_hallucinated_reply(turn.get("content","")):
            clean.append({
                "role": "assistant",
                "content": (
                    "I can only answer from our extracted records. "
                    "Please use 'look up [name or reference]' to retrieve the report first."
                ),
            })
        else:
            clean.append(turn)
    return clean


# ─────────────────────────────────────────────────────────────────────────────
# route_chat_message — identical routing logic to V1
# Step 1  scan keywords → redirect to Scan Folder screen
# Step 2  extraction   → trigger_extraction_for_chat()
# Step 3  file status  → tracking_db counts
# Step 4  log keywords → get_log_history()
# Steps 5-11 identical to V1
# ─────────────────────────────────────────────────────────────────────────────
def route_chat_message(message: str, history: list[dict]) -> str:
    history = _sanitize_history(history)
    lower   = message.lower()

    # 1. Scan
    if any(kw in lower for kw in ("scan box","scan folder","check box","scan","rescan")):
        return (
            "To scan the Local Folder, please click **📂 Scan Folder** in the sidebar "
            "and press the **Scan Local Folder** button."
        )

    # 2. Extraction
    if any(kw in lower for kw in (
        "run extract","start extract","extract now","extract files",
        "run pipeline","extract","process files","process reports",
    )):
        return trigger_extraction_for_chat()

    # 3. File status
    if any(kw in lower for kw in (
        "file status","how many files","pending files","files pending",
        "files completed","file count",
    )):
        db        = load_tracking()
        files     = db.get("files", {})
        total     = len(files)
        completed = sum(1 for f in files.values() if f.get("status") == "Completed")
        pending   = total - completed
        return (
            f"File Status Summary:\n"
            f"  Total     : {total}\n"
            f"  Completed : {completed}\n"
            f"  Pending   : {pending}"
        )

    # 4. Logs
    if any(kw in lower for kw in (
        "show logs","view logs","logs today","logs this week","logs this month",
        "logs this year","extraction log","extraction history","show log","view log","logs",
    )):
        period = ("year" if "year" in lower else "month" if "month" in lower
                  else "week" if "week" in lower else "day")
        return get_log_history(period)

    # 5. Pending-download context check
    _PENDING_MARKERS = (
        "which report would you like",
        "please specify a name",
        "no report files found for",
        "if the report hasn't been extracted",
    )
    _last_bot = next(
        (t.get("content","") for t in reversed(history) if t.get("role") == "assistant"), ""
    )
    if any(m in _last_bot.lower() for m in _PENDING_MARKERS):
        result = skill_lookup_report(message.strip())
        if not result.startswith("No reports found"):
            return result
        return (
            f"No records found matching **'{message.strip()}'** in our extracted reports.\n"
            "Please check the name or reference number and try again, "
            "or run an extraction if the report has not been processed yet."
        )

    # 6. Report download — redirect to local files
    _REPORT_PATTERNS = [
        r"generate\s+(?:me\s+)?reports?\s+(?:for\s+)?(.+)",
        r"download\s+reports?\s+(?:for\s+)?(.+)",
        r"get\s+reports?\s+(?:for\s+)?(.+)",
        r"reports?\s+for\s+(.+)",
    ]
    for _rp in _REPORT_PATTERNS:
        _rm = _re_ai.match(_rp, lower.strip(), _re_ai.IGNORECASE)
        if _rm:
            _rq = _rm.group(1).strip()
            ext_dir = _extracted_folder()
            return (
                f"The extracted files for **{_rq}** are saved locally in:\n"
                f"  • {ext_dir / 'Word Extracts'}\n"
                f"  • {ext_dir / 'CSV Extracts'}\n"
                f"  • {ext_dir / 'JSON File Extracts'}\n\n"
                f"Navigate to those folders or use 'look up {_rq}' to see the report data here."
            )

    # 7. Lookup verb patterns
    _LOOKUP_PATTERNS = [
        r"(?:look\s*up|lookup)\s+(.+)",
        r"show\s+me\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"find\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"get\s+(?:the\s+)?report\s+(?:for|of|on)\s+(.+)",
        r"tell\s+me\s+about\s+(.+)",
        r"(?:report\s+(?:for|of|on)|details?\s+(?:for|of|on)|info(?:rmation)?\s+(?:for|of|on|about))\s+(.+)",
        r"(?:display|pull\s+up)\s+(?:the\s+)?(?:report\s+(?:for|of|on)\s+)?(.+)",
        r"search\s+for\s+(.+)",
        r"(?:overall\s+status|status)\s+(?:(?:for|of|on)\s+)?(.+)",
        r"(?:adverse\s+media|global\s+sanctions|bankruptcy|financial|credit|directorship|"
        r"civil\s+litigation|professional\s+licen[sc]e|social\s+media)\s+"
        r"(?:check|screening|verification)?\s*(?:for|of|on)\s+(.+)",
    ]
    for _pat in _LOOKUP_PATTERNS:
        _m = _re_ai.match(_pat, lower.strip(), _re_ai.IGNORECASE)
        if _m:
            query = _m.group(1).strip()
            query = _re_ai.sub(r"\s*(?:please|now|thanks?|report|record|details?)\s*$", "",
                               query, flags=_re_ai.IGNORECASE).strip()
            if query and len(query) >= 3:
                result = skill_lookup_report(query)
                if not result.startswith("No reports found"):
                    return result
                return (
                    f"No records found matching **'{query}'** in our extracted reports.\n"
                    "Please check the name or reference number and try again, "
                    "or run an extraction if the report has not been processed yet."
                )

    # 8. Bare check-name guard
    _CHECK_NAME_RE = _re_ai.compile(
        r"^(?:adverse\s+media|global\s+sanctions|bankruptcy|financial(?:/credit)?|"
        r"credit|directorship|civil\s+litigation|professional\s+licen[sc]e|"
        r"social\s+media)\s*(?:check|screening|verification)?$", _re_ai.IGNORECASE,
    )
    if _CHECK_NAME_RE.match(lower.strip()):
        return (
            f"Which person's **{message.strip()}** result would you like to see?\n"
            f"Please use: **'look up [name]'** or **'{message.strip()} for [name]'**"
        )

    # 9. Bare name/ref guard
    _PREFIX_STRIP = _re_ai.compile(
        r"^(?:overall\s+status|status|report|details?|info(?:rmation)?)\s+(?:(?:for|of|on|about)\s+)?",
        _re_ai.IGNORECASE,
    )
    _reserved = {
        "scan","rescan","extract","status","logs","log","help",
        "hello","hi","hey","yes","no","ok","okay","sure",
        "thanks","thank","clear","quit","exit",
        "insights","dashboard","home","check","check box",
        "file insights","show file insights","show insights",
        "view insights","show dashboard","view dashboard",
        "show status","show file status","view file status",
        "overall status","what is the overall status",
        "pipeline","run pipeline","process",
    }
    _bare       = _PREFIX_STRIP.sub("", message.strip()).strip()
    _bare_lower = _bare.lower()
    if (
        len(_bare) >= 3 and len(_bare) <= 60
        and _bare_lower not in _reserved
        and lower.strip() not in _reserved
        and _re_ai.search(r"[a-zA-Z]", _bare)
        and len(_bare.split()) <= 5
        and not _re_ai.search(r"\s{2,}", _bare)
    ):
        _bare_result = skill_lookup_report(_bare)
        if not _bare_result.startswith("No reports found"):
            return _bare_result
        return (
            f"No records found matching **'{_bare}'** in our extracted reports.\n"
            "Please check the name or reference number and try again, "
            "or run an extraction if the report has not been processed yet."
        )

    # 10. Affirmative follow-up
    _affirmative = {
        "yes","yeah","yep","sure","show","view","show me","show details",
        "view details","full report","full details","show report","view report",
        "show full","view full","more details","more info","see more",
        "overall status","status",
    }
    if lower.strip() in _affirmative or lower.strip().startswith(("yes ","show ","view ")):
        for turn in reversed(history):
            if turn.get("role") == "assistant":
                prev = turn.get("content","")
                subj_match = _re_ai.search(r"Subject:\s*([^\|]+)", prev)
                if subj_match:
                    return skill_lookup_report(subj_match.group(1).strip())
                break

    # 11. LLM (Granite → Groq)
    cfg = _load_ai_config()

    grounded_context = None
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            prev = turn.get("content","")
            if _re_ai.search(r"Subject:\s*[^\|]+\|", prev):
                grounded_context = prev
                break

    _REPORT_INQUIRY_RE = _re_ai.compile(
        r"(?:yes|yeah|yep|sure|show|view|full\s+report|full\s+details?|"
        r"more\s+(?:details?|info)|see\s+more|tell\s+me\s+more|"
        r"what\s+(?:is|are|was|were)|who\s+is|background\s+check|"
        r"criminal\s+record|employment\s+(?:history|verification)|"
        r"identity\s+verif|education|reference\s+check|"
        r"report\s+(?:for|of|on|details?)|check\s+result)", _re_ai.IGNORECASE,
    )
    if not grounded_context and _REPORT_INQUIRY_RE.search(lower):
        return (
            "I don't have any extracted records loaded in this conversation yet.\n\n"
            "Please use **'look up [name or reference]'** to retrieve a report first, "
            "then ask your question — I'll answer only from that data."
        )

    def _build_anchored_history(hist):
        if not grounded_context:
            return hist
        return [{"role": "system", "content": (
            "The following is the ONLY data you are permitted to use when "
            "answering questions about this person. Do not add, infer, or "
            "invent anything beyond what is listed here.\n\nEXTRACTED RECORD:\n"
            + grounded_context
        )}] + hist

    _HALLUCINATION_BLOCKED = (
        "I can only answer from our extracted records. "
        "Please use 'look up [name or reference]' to retrieve the report first, "
        "then ask your question."
    )

    granite_ready = (
        cfg.get("watsonx",{}).get("api_key","") not in ("","YOUR_WATSONX_API_KEY")
        and cfg.get("watsonx",{}).get("project_id","") not in ("","YOUR_WATSONX_PROJECT_ID")
        and not cfg.get("watsonx",{}).get("project_id","").startswith("ApiKey-")
    )
    if granite_ready:
        try:
            reply = granite_chat(_build_anchored_history(history), message)
            if _is_hallucinated_reply(reply):
                return _HALLUCINATION_BLOCKED
            return reply
        except Exception:
            pass

    groq_ready = cfg.get("groq",{}).get("api_key","") not in ("","YOUR_GROQ_API_KEY")
    if groq_ready:
        try:
            reply = groq_chat(_build_anchored_history(history), message)
            if _is_hallucinated_reply(reply):
                return _HALLUCINATION_BLOCKED
            return reply
        except Exception as exc:
            return f"⚠ LLM error: {str(exc)[:200]}"

    return (
        "Hi! I'm Detective Conan. I can help with:\n"
        "• 'look up [name]'      — search extracted reports\n"
        "• 'sync'               — sync Box folder to Local Folder\n"
        "• 'extract'             — run the extraction pipeline\n"
        "• 'file status'         — show Pending / Completed counts\n"
        "• 'logs this week'      — view extraction log history\n\n"
        "Configure watsonx or groq credentials in config.json to enable full AI responses."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Chat Frame
# ══════════════════════════════════════════════════════════════════════════════
class ChatFrame(tk.Frame):
    """AI Assistant — identical UI to V1, grounded on Local Folder JSON extracts."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app      = app
        self._history: list[dict] = []
        self._busy    = False

        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="AI Assistant", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")
        tk.Button(
            hdr, text="🗑  Clear Chat",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            padx=8, pady=4, command=self._clear_chat,
        ).pack(side="right")
        self._model_var = tk.StringVar(value="Model: —")
        tk.Label(hdr, textvariable=self._model_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(side="right", padx=12)

        chat_outer = tk.Frame(self, bg=CLR_BG)
        chat_outer.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        self._chat_display = tk.Text(
            chat_outer, bg=CLR_WHITE, fg=CLR_TEXT,
            font=("Segoe UI", 10), relief="flat", wrap="word",
            state="disabled", highlightbackground="#E5E7EB", highlightthickness=1,
            padx=12, pady=8, cursor="arrow",
        )
        chat_sb = ttk.Scrollbar(chat_outer, orient="vertical",
                                command=self._chat_display.yview)
        self._chat_display.configure(yscrollcommand=chat_sb.set)
        self._chat_display.pack(side="left", fill="both", expand=True)
        chat_sb.pack(side="right", fill="y")
        self._chat_display.tag_configure("user",      foreground="#1F3864", font=("Segoe UI",10,"bold"))
        self._chat_display.tag_configure("assistant", foreground="#22863A", font=("Segoe UI",10))
        self._chat_display.tag_configure("system",    foreground=CLR_MUTED,  font=("Segoe UI",9,"italic"))
        self._chat_display.tag_configure("error",     foreground=CLR_ORANGE, font=("Segoe UI",9,"italic"))

        input_frame = tk.Frame(self, bg=CLR_BG)
        input_frame.pack(fill="x", padx=24, pady=(0, 16))
        self._input_var = tk.StringVar()
        self._input_box = tk.Entry(
            input_frame, textvariable=self._input_var,
            font=("Segoe UI", 10), relief="flat",
            bg=CLR_WHITE, fg=CLR_TEXT,
            highlightbackground="#E5E7EB", highlightthickness=1,
        )
        self._input_box.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._input_box.bind("<Return>", lambda e: self._send())
        self._send_btn = tk.Button(
            input_frame, text="  Send  ",
            bg=CLR_GREEN, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat", cursor="hand2",
            padx=10, pady=6, command=self._send,
        )
        self._send_btn.pack(side="right")
        self._typing_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._typing_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24, pady=(0,4))

    def on_show(self):
        if not self._history:
            self._append_message("system",
                "Hello! I'm Detective Conan, your AI Assistant (V2).\n"
                "I work from the Local Folder — Sync & Scan first!\n\n"
                "Check Results\n"
                "  'look up [name]'  |  'status of [ref]'\n\n"
                "Extract / Sync\n"
                "  'run extraction'  |  'extract files'\n\n"
                "Logs & Status\n"
                "  'logs this week'  |  'file status'"
            )
        try:
            cfg = _load_ai_config()
            wx  = cfg.get("watsonx",{})
            gc  = cfg.get("groq",{})
            granite_ok = (
                wx.get("api_key","") not in ("","YOUR_WATSONX_API_KEY")
                and wx.get("project_id","") not in ("","YOUR_WATSONX_PROJECT_ID")
                and not wx.get("project_id","").startswith("ApiKey-")
            )
            if granite_ok:
                self._model_var.set(f"Model: {wx.get('model_id','granite')}")
            elif gc.get("api_key","") not in ("","YOUR_GROQ_API_KEY"):
                self._model_var.set(f"Model: {gc.get('model','llama-3.3-70b')}")
            else:
                self._model_var.set("Model: not configured")
        except Exception:
            self._model_var.set("Model: config error")
        self._input_box.focus_set()

    def _append_message(self, role: str, text: str):
        self._chat_display.config(state="normal")
        if role == "user":
            self._chat_display.insert("end", "\nYou:  ", "user")
            self._chat_display.insert("end", text + "\n", "user")
        elif role == "assistant":
            self._chat_display.insert("end", "\nAssistant:  ", "assistant")
            self._chat_display.insert("end", text + "\n", "assistant")
        elif role == "system":
            self._chat_display.insert("end", text + "\n", "system")
        else:
            self._chat_display.insert("end", f"\n⚠ {text}\n", "error")
        self._chat_display.config(state="disabled")
        self._chat_display.see("end")

    def _clear_chat(self):
        self._history = []
        self._chat_display.config(state="normal")
        self._chat_display.delete("1.0","end")
        self._chat_display.config(state="disabled")
        self.on_show()

    def _send(self):
        text = self._input_var.get().strip()
        if not text or self._busy:
            return
        self._input_var.set("")
        self._input_box.config(state="disabled")
        self._send_btn.config(state="disabled")
        self._busy = True
        self._append_message("user", text)
        self._typing_var.set("Assistant is thinking…")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, user_message: str):
        try:
            reply = route_chat_message(user_message, list(self._history))
            self._history.append({"role": "user",      "content": user_message})
            self._history.append({"role": "assistant", "content": reply})
            if len(self._history) > 40:
                self._history = self._history[-40:]
            self.after(0, lambda r=reply: self._on_reply(r))
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _on_reply(self, reply: str):
        self._typing_var.set("")
        self._append_message("assistant", reply)
        self._busy = False
        self._input_box.config(state="normal")
        self._send_btn.config(state="normal")
        self._input_box.focus_set()

    def _on_error(self, msg: str):
        self._typing_var.set("")
        self._append_message("error", msg[:300])
        self._busy = False
        self._input_box.config(state="normal")
        self._send_btn.config(state="normal")


# ─────────────────────────────────────────────────────────────────────────────
# Startup folder bootstrap — ensures all required local folders exist before
# the app starts, so no screen ever encounters a missing directory.
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_folders() -> None:
    """
    Create every folder that the app reads from or writes to, if it does not
    already exist.  Uses mkdir(parents=True, exist_ok=True) so it is safe to
    call on every startup regardless of current state.

    Folders created here
    ────────────────────
    • Log History/                     — log viewer + per-file extraction logs
    • Local Folder/                    — Box sync destination (also created lazily
                                         by _local_folder(), but done here too so
                                         the folder is visible before first sync)
    • Local Folder/Extracted/          — root for all output files
    • Local Folder/Extracted/Word Extracts/
    • Local Folder/Extracted/CSV Extracts/
    • Local Folder/Extracted/JSON File Extracts/
    """
    try:
        cfg = _read_config()
    except Exception:
        cfg = {}

    local_rel     = cfg.get("local", {}).get("local_folder",    "Local Folder")
    extracted_rel = cfg.get("local", {}).get("extracted_folder","Local Folder/Extracted")

    local_path     = Path(local_rel)     if Path(local_rel).is_absolute()     else BASE_DIR / local_rel
    extracted_path = Path(extracted_rel) if Path(extracted_rel).is_absolute() else BASE_DIR / extracted_rel

    folders = [
        LOG_HISTORY_DIR,
        local_path,
        extracted_path,
        extracted_path / "Word Extracts",
        extracted_path / "CSV Extracts",
        extracted_path / "JSON File Extracts",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _ensure_folders()
    app = PDFExtractorAppV2()
    app.mainloop()
