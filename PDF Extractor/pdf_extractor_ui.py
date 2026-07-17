"""
Background Check Report Automation — Desktop UI
================================================
NOTE: To run without a console/terminal window, use Launch.vbs (double-click)
instead of running python pdf_extractor_ui.py directly.
================================================
Tkinter-based interface for the PDF extraction pipeline.

Screens (sidebar navigation):
  🏠 Home          — landing page with shortcut cards to each feature
  📂 Check Box     — lists PDF files found in the configured Box folder;
                     only shows files with Pending status (Completed are hidden)
  📊 Insights      — bar chart of Completed vs Pending extractions,
                     filterable by Day / Week / Month / Year
  ⚙️ Extract Files — runs the full extraction pipeline, moves processed PDFs
                     to the Box Archive folder, writes per-file log files, and
                     shows a result card for each processed file
  💬 AI Assistant  — ICA-powered chatbot that can answer questions about
                     the extracted reports and trigger Scan / Extract actions
                     via natural language commands

All network operations (Box API calls) run on background threads so the UI
never freezes. UI updates from those threads are posted back via self.after(0, …).

Log files are written to:
  Log History / YYYY / MMM_YYYY / Week_NN / YYYY-MM-DD / <RefNo>_YYYYMMDD_HHMMSS.log

Tracking state (Pending / Completed per Box file ID) is persisted in:
  tracking_db.json  (created alongside this script at runtime)
"""

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext   # scrolledtext kept for future use
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import importlib.util                               # used to load the extractor module at runtime


# ─────────────────────────────────────────────────────────────────────────────
# Module-level path constants
# All paths are resolved relative to the directory containing this script.
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent.resolve()   # directory of this script
CONFIG_PATH     = BASE_DIR / "config.json"          # Box credentials + settings
TRACKING_PATH   = BASE_DIR / "tracking_db.json"     # per-file extraction state DB
LOG_HISTORY_DIR = BASE_DIR / "Log History"          # root of the per-file log tree


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette — keep all colours in one place for easy theming
# ─────────────────────────────────────────────────────────────────────────────
CLR_BG      = "#F0F4F8"   # main content area background
CLR_SIDEBAR = "#1F3864"   # dark-navy sidebar background
CLR_ACCENT  = "#2E75B6"   # medium blue — active nav, scan button
CLR_WHITE   = "#FFFFFF"   # card / widget backgrounds
CLR_TEXT    = "#1F2328"   # primary text
CLR_MUTED   = "#57606A"   # secondary / hint text
CLR_GREEN   = "#22863A"   # success — Completed badge
CLR_ORANGE  = "#D1622A"   # failure — error badge
CLR_PENDING = "#E6A817"   # warning amber — Pending badge

# ─────────────────────────────────────────────────────────────────────────────
# Font definitions
# ─────────────────────────────────────────────────────────────────────────────
FONT_TITLE = ("Segoe UI", 14, "bold")   # page heading
FONT_LABEL = ("Segoe UI", 10)           # sidebar nav items, general labels
FONT_BOLD  = ("Segoe UI", 10, "bold")   # field labels, card titles
FONT_SMALL = ("Segoe UI", 9)            # captions, status bars, badges
FONT_MONO  = ("Consolas", 9)            # monospace (reserved for future log display)


# ─────────────────────────────────────────────────────────────────────────────
# Tracking database helpers
# tracking_db.json holds a top-level "files" dict keyed by Box file ID.
# Each value stores: name, status, last_extracted, ref_number, archived.
# ─────────────────────────────────────────────────────────────────────────────
def load_tracking() -> dict:
    """
    Read and return tracking_db.json as a dict.
    Returns {"files": {}} if the file does not yet exist (first run).
    """
    if TRACKING_PATH.exists():
        with open(TRACKING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}}   # default empty state


def save_tracking(db: dict) -> None:
    """Persist the in-memory tracking dict back to tracking_db.json."""
    with open(TRACKING_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def get_box_client():
    """
    Read config.json, build an authenticated Box SDK Client, and return
    (client, cfg) so the caller can also access folder IDs from cfg.

    NOTE: Developer Tokens expire after 60 minutes. Refresh the token in
    config.json → box.access_token before running another extraction.
    """
    from boxsdk import OAuth2, Client
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    box  = cfg["box"]
    # OAuth2 with a pre-issued access_token — no automatic refresh
    auth = OAuth2(
        client_id=box["client_id"],
        client_secret=box["client_secret"],
        access_token=box["access_token"],
    )
    return Client(auth), cfg


# ─────────────────────────────────────────────────────────────────────────────
# Folder hierarchy builder — used for extract output folders
# Mirrors the same structure used by the extractor's build_extract_folder().
# ─────────────────────────────────────────────────────────────────────────────
def build_extract_folder(base_dir: Path, when: datetime) -> Path:
    """
    Build (and create) the correct daily output folder path:
      base_dir / YYYY / MMM_YYYY_Extracts / Week_NN / YYYY-MM-DD

    Returns the fully created daily folder Path.
    """
    year_folder   = base_dir / str(when.year)
    month_folder  = year_folder / f"{when.strftime('%b_%Y')}_Extracts"
    week_num      = when.isocalendar()[1]           # ISO week number
    weekly_folder = month_folder / f"Week_{week_num:02d}"
    daily_folder  = weekly_folder / when.strftime("%Y-%m-%d")
    daily_folder.mkdir(parents=True, exist_ok=True)
    return daily_folder


# ─────────────────────────────────────────────────────────────────────────────
# Per-file extraction log writer
# ─────────────────────────────────────────────────────────────────────────────
def write_extraction_log(ref_number: str, when: datetime, content: str) -> Path:
    """
    Write a plain-text extraction log to the Log History folder tree:
      Log History / YYYY / MMM_YYYY / Week_NN / YYYY-MM-DD / <RefNo>_YYYYMMDD_HHMMSS.log

    ref_number — used as the filename prefix; illegal filename characters are
                 replaced with underscores.
    when       — the datetime of the extraction run (determines folder path).
    content    — the full log text to write.

    Returns the Path of the written .log file.
    """
    import re as _re

    # Build the folder hierarchy for this log entry
    year_folder  = LOG_HISTORY_DIR / str(when.year)
    month_folder = year_folder     / when.strftime("%b_%Y")
    week_num     = when.isocalendar()[1]
    week_folder  = month_folder    / f"Week_{week_num:02d}"
    day_folder   = week_folder     / when.strftime("%Y-%m-%d")
    day_folder.mkdir(parents=True, exist_ok=True)

    # Sanitise ref_number: replace characters that are illegal in Windows filenames
    safe_ref  = _re.sub(r'[<>:"/\\|?*]', "_", ref_number).strip() or "UNKNOWN_REF"
    timestamp = when.strftime("%Y%m%d_%H%M%S")
    log_path  = day_folder / f"{safe_ref}_{timestamp}.log"

    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    return log_path


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Root application window
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class PDFExtractorApp(tk.Tk):
    """
    Main application window.
    Builds a fixed left sidebar for navigation and a right content area where
    all feature frames (Home, CheckBox, Insights, Extract) are stacked on top
    of each other — only the active frame is raised to the top.
    """

    def __init__(self):
        super().__init__()
        self.title("Background Check Report Automation")
        self.geometry("1100x700")       # default window size
        self.minsize(900, 600)          # minimum usable size
        self.configure(bg=CLR_BG)
        self.resizable(True, True)      # allow free resizing

        # Load tracking DB into memory so frames can access it without re-reading disk
        self.db = load_tracking()

        self._build_layout()            # create sidebar + content area
        self._show_frame("home")        # open the Home screen on launch

    # ── Layout construction ───────────────────────────────────────────────────
    def _build_layout(self):
        """
        Build the two-panel layout:
          Left:  fixed-width dark sidebar with navigation buttons
          Right: full-height content area housing all feature frames
        """
        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = tk.Frame(self, bg=CLR_SIDEBAR, width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)   # prevent sidebar from shrinking to fit children

        # App title in the sidebar header
        tk.Label(
            sidebar,
            text="Background Check\nReport Automation",
            bg=CLR_SIDEBAR, fg=CLR_WHITE,
            font=("Segoe UI", 11, "bold"),
            pady=20,
        ).pack(fill="x")

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=12)

        # Navigation items: (display label, frame key)
        nav_items = [
            ("🏠  Home",          "home"),
            ("📂  Check Box",     "check"),
            ("📊  Insights",      "insights"),
            ("⚙️  Extract Files", "extract"),
            ("💬  AI Assistant",  "chat"),
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
                command=lambda k=key: self._show_frame(k),   # capture key in closure
            )
            btn.pack(fill="x")
            self._nav_btns[key] = btn   # store reference for highlight toggling

        # Version label at the bottom of the sidebar
        tk.Label(
            sidebar, text="v1.0.0",
            bg=CLR_SIDEBAR, fg="#7090B0",
            font=FONT_SMALL,
        ).pack(side="bottom", pady=8)

        # ── Content area ──────────────────────────────────────────────────────
        self._content = tk.Frame(self, bg=CLR_BG)
        self._content.pack(side="left", fill="both", expand=True)

        # Instantiate all frames and stack them via .place() so they overlap
        self._frames = {}
        for key, cls in [
            ("home",     HomeFrame),
            ("check",    CheckBoxFrame),
            ("insights", InsightsFrame),
            ("extract",  ExtractFrame),
            ("chat",     ChatFrame),
        ]:
            frame = cls(self._content, self)
            # Place each frame to fill the entire content area
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._frames[key] = frame

    def _show_frame(self, key: str):
        """
        Raise the named frame to the top and update the sidebar highlight.
        on_show() is called after a brief defer (self.after(0)) so the frame
        becomes visible before any data-loading work begins — prevents UI lag.
        """
        # Update sidebar button colours: active = accent blue, inactive = dark navy
        for k, btn in self._nav_btns.items():
            btn.config(bg=CLR_ACCENT if k == key else CLR_SIDEBAR)

        frame = self._frames[key]
        frame.lift()   # bring this frame above all sibling frames

        # Defer on_show so the frame paints first, then loads/refreshes data
        if hasattr(frame, "on_show"):
            self.after(0, frame.on_show)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Home Frame — landing page with three shortcut cards
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class HomeFrame(tk.Frame):
    """
    Landing screen shown on app startup.
    Displays a subtitle and three clickable cards that navigate to the
    Check Box, Insights, and Extract Files screens respectively.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app = app

        # Page subtitle (the large title was removed as requested)
        tk.Label(
            self,
            text="Background Check Report Automation",
            bg=CLR_BG, fg=CLR_MUTED,
            font=("Segoe UI", 12),
        ).pack(pady=(50, 6))

        # Visual divider between subtitle and cards
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=80, pady=30)

        # Row of three feature cards
        cards_frame = tk.Frame(self, bg=CLR_BG)
        cards_frame.pack()

        cards = [
            ("📂", "Check Box Folder",
             "Scan your Box folder for PDF files\nand see their extraction status.",
             "check"),
            ("📊", "Insights",
             "View charts and statistics on\nextraction progress over time.",
             "insights"),
            ("⚙️", "Extract Files",
             "Run the extraction pipeline and\narchive processed PDF files.",
             "extract"),
            ("💬", "AI Assistant",
             "Chat with IBM Consulting\nAdvantage AI assistant.",
             "chat"),
        ]
        for icon, title, desc, key in cards:
            self._make_card(cards_frame, icon, title, desc, key)

    def _make_card(self, parent, icon: str, title: str, desc: str, key: str):
        """
        Build a single white clickable card widget and pack it into *parent*.
        Clicking anywhere on the card navigates to the frame identified by *key*.
        """
        card = tk.Frame(
            parent,
            bg=CLR_WHITE,
            relief="flat",
            cursor="hand2",
            highlightbackground="#E5E7EB",
            highlightthickness=1,
        )
        card.pack(side="left", padx=14, pady=10, ipadx=16, ipady=14)

        # Bind the click handler on both the card frame AND every child label —
        # clicks on child widgets do not bubble up to the parent frame in Tkinter,
        # so each widget needs its own binding to ensure the whole card is clickable.
        nav = lambda e, k=key: self.app._show_frame(k)
        card.bind("<Button-1>", nav)

        lbl_icon  = tk.Label(card, text=icon,  bg=CLR_WHITE, font=("Segoe UI", 24))
        lbl_title = tk.Label(card, text=title, bg=CLR_WHITE, fg=CLR_TEXT,  font=FONT_BOLD)
        lbl_desc  = tk.Label(card, text=desc,  bg=CLR_WHITE, fg=CLR_MUTED, font=FONT_SMALL, justify="center")

        lbl_icon.pack()
        lbl_title.pack(pady=(4, 2))
        lbl_desc.pack()

        # Propagate click to each child label so the full card area is responsive
        lbl_icon.bind("<Button-1>",  nav)
        lbl_title.bind("<Button-1>", nav)
        lbl_desc.bind("<Button-1>",  nav)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Check Box Frame — scan Box folder and display Pending files
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class CheckBoxFrame(tk.Frame):
    """
    Displays PDF files found in the configured Box source folder.

    Only files with status "Pending" are shown in the table — Completed files
    are counted in the summary bar but excluded from the list to reduce noise.

    The Scan operation runs on a background thread so the UI stays responsive.
    The scan always resets any file found in the source folder to "Pending"
    regardless of its previous state, because if it is still in the source
    folder it has not yet been successfully extracted and archived.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app = app

        # ── Header row (title + scan button) ─────────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Check Box Folder", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")
        # Store a reference to the scan button so we can disable it during scanning
        self._scan_btn = tk.Button(
            hdr,
            text="  ðŸ”„  Scan Box Folder  ",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat",
            cursor="hand2", padx=8, pady=6,
            command=self._scan,
        )
        self._scan_btn.pack(side="right")

        # ── Summary counts bar ────────────────────────────────────────────────
        # Shows Total / Completed / Pending counts above the table
        self._summary_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._summary_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24)

        # ── Status bar at the bottom (packed first so it anchors to bottom) ──
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(side="bottom", pady=6)

        # ── File table + empty-state label in a shared container ─────────────
        # Both widgets live inside table_frame; only one is visible at a time.
        table_frame = tk.Frame(self, bg=CLR_BG)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        cols = ("File Name", "Box File ID", "Status", "Last Extracted", "Reference No.")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        widths = [320, 120, 90, 160, 160]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")

        # Colour-code rows by status (only "pending" tag is used; completed are hidden)
        self._tree.tag_configure("pending", foreground=CLR_ORANGE)

        # Vertical scrollbar for the table
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        # Empty-state label — overlaid via place() when there are no Pending files
        self._empty_label = tk.Label(
            table_frame,
            text="No File(s) available on the folder",
            bg=CLR_WHITE, fg=CLR_MUTED,
            font=("Segoe UI", 11),
            highlightbackground="#E5E7EB",
            highlightthickness=1,
        )
        # Not visible on startup — shown/hidden by _populate_from_db()

    def on_show(self):
        """Called by _show_frame when this screen becomes active. Refreshes the table."""
        self._populate_from_db()

    def _populate_from_db(self):
        """
        Read tracking_db.json and rebuild the table.
        Only Pending files are shown. When there are none, the tree is hidden
        and a 'No File(s) available on the folder' label is displayed instead.
        """
        self._tree.delete(*self._tree.get_children())   # clear existing rows
        db      = load_tracking()
        files   = db.get("files", {})
        pending = completed = 0

        for fid, info in files.items():
            status = info.get("status", "Pending")
            if status == "Pending":
                pending += 1
                # Insert row with orange "pending" tag
                self._tree.insert("", "end", values=(
                    info.get("name",           ""),
                    fid,
                    status,
                    info.get("last_extracted", "--"),
                    info.get("ref_number",     "--"),
                ), tags=("pending",))
            else:
                completed += 1

        # Update the summary counts bar
        self._summary_var.set(
            f"Total: {len(files)}   |   ✅ Completed: {completed}   |   🕐 Pending: {pending}"
        )

        # Show the empty-state label when no Pending files exist; restore table otherwise
        if pending == 0:
            self._tree.pack_forget()
            self._empty_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self._empty_label.place_forget()
            if not self._tree.winfo_ismapped():
                self._tree.pack(side="left", fill="both", expand=True)

    def _scan(self):
        """
        Entry point for the Scan button.
        Disables the button immediately (to prevent double-clicks) and starts
        the Box API call on a background thread.
        """
        self._scan_btn.config(state="disabled", text="  ⏳  Scanning…  ")
        self._status_var.set("Scanning Box folder…")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        """
        Background thread: connects to Box, lists PDF files in the source folder,
        and resets any found file to "Pending" in the tracking DB.

        Resetting to Pending on every scan is intentional: if a file is still
        in the source folder, it either hasn't been extracted yet or a previous
        extraction attempt failed — it should be available for extraction again.

        All UI updates are posted back to the main thread via self.after(0, …).
        """
        try:
            client, cfg = get_box_client()
            folder_id   = cfg["box"]["folder_id"]   # source folder to scan
            db          = load_tracking()

            # Fetch up to 1 000 items (adequate for typical volumes)
            items = list(client.folder(folder_id).get_items(limit=1000))
            found = 0

            for item in items:
                if item.type == "file" and item.name.lower().endswith(".pdf"):
                    found += 1
                    existing = db.get("files", {}).get(item.id, {})
                    # Always set status to Pending for files still in the source folder.
                    # Preserve historical last_extracted and ref_number if they exist.
                    db["files"][item.id] = {
                        "name":           item.name,
                        "status":         "Pending",
                        "last_extracted": existing.get("last_extracted"),
                        "ref_number":     existing.get("ref_number"),
                        "archived":       False,
                    }

            save_tracking(db)
            self.app.db = db   # update the app-level reference

            # Post UI updates back to the main thread
            self.after(0, self._populate_from_db)
            self.after(0, lambda: self._status_var.set(
                f"Scan complete — {found} PDF(s) found in Box folder."
            ))

        except Exception as exc:
            # Show a concise inline error in the status bar — no popup.
            # A 401/400 from Box almost always means the Developer Token has
            # expired. The user just needs to update access_token in config.json.
            err_text = str(exc)
            if "401" in err_text or "400" in err_text or "invalid_token" in err_text:
                msg = "âš  Box token expired — update access_token in config.json and scan again."
            else:
                msg = f"âš  Scan failed: {err_text[:120]}"
            self.after(0, lambda m=msg: self._status_var.set(m))

        finally:
            # Always re-enable the scan button regardless of success or failure
            self.after(0, lambda: self._scan_btn.config(
                state="normal", text="  ðŸ”„  Scan Box Folder  "
            ))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Insights Frame — extraction statistics bar chart
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class InsightsFrame(tk.Frame):
    """
    Displays a bar chart of extraction counts bucketed by time period.
    Each period shows two bars side-by-side: Completed (green) and Pending (amber).

    The chart is drawn directly onto a tk.Canvas using primitive shapes — no
    external charting library is required. The canvas redraws on resize.

    Filter options: Day / Week / Month / Year (radio buttons).
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app     = app
        self._filter = tk.StringVar(value="Month")   # default time grouping

        # ── Header row (title + filter controls) ─────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="Extraction Insights", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")

        # Time-period filter radio buttons + Refresh button
        filter_frame = tk.Frame(hdr, bg=CLR_BG)
        filter_frame.pack(side="right")
        for opt in ("Day", "Week", "Month", "Year"):
            tk.Radiobutton(
                filter_frame,
                text=opt,
                variable=self._filter, value=opt,
                bg=CLR_BG, fg=CLR_TEXT,
                font=FONT_LABEL,
                activebackground=CLR_BG, selectcolor=CLR_BG,
                cursor="hand2",
                command=self._refresh,   # re-draw chart whenever filter changes
            ).pack(side="left", padx=4)
        tk.Button(
            filter_frame, text="Refresh",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            command=self._refresh,
        ).pack(side="left", padx=(10, 0))

        # ── Summary cards row (Total / Completed / Pending) ───────────────────
        # Rebuilt on every refresh — children are destroyed and re-created
        self._cards_frame = tk.Frame(self, bg=CLR_BG)
        self._cards_frame.pack(fill="x", padx=24, pady=(0, 10))

        # ── Chart canvas ──────────────────────────────────────────────────────
        self._canvas = tk.Canvas(
            self, bg=CLR_WHITE,
            highlightbackground="#E5E7EB", highlightthickness=1,
        )
        self._canvas.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        # Redraw the chart whenever the canvas is resized
        self._canvas.bind("<Configure>", lambda e: self._draw_chart())

        self._chart_data: dict = {}   # {period_key: {"Pending": n, "Completed": n}}

    def on_show(self):
        """Called when this screen becomes active. Refreshes data and redraws chart."""
        self._refresh()

    def _refresh(self):
        """
        Read tracking_db.json, bucket files by the selected time period,
        rebuild the summary cards, and redraw the bar chart.
        """
        db     = load_tracking()
        files  = db.get("files", {})
        period = self._filter.get()
        now    = datetime.now()

        # Bucket each file into its time-period key based on last_extracted date.
        # Files with no extraction date (Pending) are bucketed into the current period.
        buckets: dict[str, dict] = defaultdict(lambda: {"Pending": 0, "Completed": 0})

        for info in files.values():
            status = info.get("status", "Pending")
            ts     = info.get("last_extracted")

            if ts:
                try:
                    dt = datetime.fromisoformat(ts)   # parse stored ISO timestamp
                except ValueError:
                    dt = now   # fall back to now if timestamp is malformed
            else:
                dt = now   # pending files with no timestamp go into the current period

            # Build the bucket key from the datetime based on the selected period
            if period == "Day":
                key = dt.strftime("%Y-%m-%d")
            elif period == "Week":
                iso = dt.isocalendar()
                key = f"{iso[0]}-W{iso[1]:02d}"
            elif period == "Month":
                key = dt.strftime("%b %Y")
            else:   # Year
                key = str(dt.year)

            buckets[key][status] += 1

        # Sort buckets chronologically by key (string sort works for ISO-format keys)
        self._chart_data = dict(sorted(buckets.items()))

        # ── Rebuild summary cards ─────────────────────────────────────────────
        for w in self._cards_frame.winfo_children():
            w.destroy()   # remove old cards before creating new ones

        total     = len(files)
        completed = sum(1 for i in files.values() if i.get("status") == "Completed")
        pending   = total - completed

        for label, val, colour in [
            ("Total Files",  total,     CLR_ACCENT),
            ("✅ Completed", completed, CLR_GREEN),
            ("🕐 Pending",   pending,   CLR_PENDING),
        ]:
            card = tk.Frame(self._cards_frame, bg=colour, padx=20, pady=12)
            card.pack(side="left", padx=6, ipadx=6)
            tk.Label(card, text=str(val),  bg=colour, fg=CLR_WHITE,
                     font=("Segoe UI", 18, "bold")).pack()
            tk.Label(card, text=label,     bg=colour, fg=CLR_WHITE,
                     font=FONT_SMALL).pack()

        self._draw_chart()

    def _draw_chart(self):
        """
        Draw the grouped bar chart onto self._canvas.
        Each time-period bucket gets two bars: Completed (green) and Pending (amber).
        The chart is redrawn from scratch on every call (canvas is cleared first).
        Exits early if there is no data or the canvas has not been sized yet.
        """
        c = self._canvas
        c.delete("all")   # clear any previous drawing

        if not self._chart_data:
            # Show a placeholder message when there is nothing to chart
            c.create_text(
                c.winfo_width() // 2, c.winfo_height() // 2,
                text="No data — scan Box folder first.",
                fill=CLR_MUTED, font=FONT_LABEL,
            )
            return

        W = c.winfo_width()
        H = c.winfo_height()
        if W < 10 or H < 10:
            return   # canvas not yet sized — drawing would be nonsensical

        # Chart margins: left (Y axis labels), right, top, bottom (X axis labels)
        pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 60
        keys    = list(self._chart_data.keys())
        n       = len(keys)
        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b

        # Determine the Y-axis scale from the tallest stacked bar
        max_v = max(
            (v["Pending"] + v["Completed"] for v in self._chart_data.values()),
            default=1,
        ) or 1

        # Bar width and gap derived from available chart width and number of groups
        bar_w = max(6, chart_w // (n * 2 + 1))
        gap   = bar_w // 2

        # ── Draw axes ─────────────────────────────────────────────────────────
        c.create_line(pad_l, pad_t, pad_l, H - pad_b, fill=CLR_MUTED, width=1)   # Y axis
        c.create_line(pad_l, H - pad_b, W - pad_r, H - pad_b, fill=CLR_MUTED, width=1)   # X axis

        # ── Draw Y-axis gridlines and labels (5 evenly spaced ticks) ─────────
        for i in range(5):
            y_val = max_v * i / 4
            y_px  = H - pad_b - int(chart_h * i / 4)
            # Dashed horizontal gridline
            c.create_line(pad_l, y_px, W - pad_r, y_px, fill="#E5E7EB", dash=(2, 4))
            # Numeric label to the left of the Y axis
            c.create_text(pad_l - 6, y_px, text=str(int(y_val)),
                          anchor="e", fill=CLR_MUTED, font=FONT_SMALL)

        # ── Draw bars and X-axis labels for each time-period bucket ───────────
        slot = chart_w / n   # horizontal space allocated per group of bars

        for idx, key in enumerate(keys):
            data   = self._chart_data[key]
            # x_base is the left edge of the first bar in this group
            x_base = pad_l + int(idx * slot + slot / 2) - bar_w - gap // 2

            for j, (status, colour) in enumerate(
                [("Completed", CLR_GREEN), ("Pending", CLR_PENDING)]
            ):
                val  = data[status]
                bh   = int(chart_h * val / max_v) if max_v else 0   # bar height in pixels
                x0   = x_base + j * (bar_w + gap)
                y0   = H - pad_b - bh
                x1   = x0 + bar_w
                y1   = H - pad_b
                # Draw the bar rectangle
                c.create_rectangle(x0, y0, x1, y1, fill=colour, outline="", tags="bar")
                # Show the count value inside the bar (only if tall enough to fit)
                if bh > 12:
                    c.create_text(
                        (x0 + x1) // 2, y0 + 6,
                        text=str(val),
                        fill=CLR_WHITE, font=("Segoe UI", 7, "bold"),
                    )

            # X-axis label — truncate long keys to last 7 characters for readability
            lbl = key if len(key) <= 10 else key[-7:]
            c.create_text(
                pad_l + int(idx * slot + slot / 2), H - pad_b + 14,
                text=lbl, fill=CLR_TEXT, font=FONT_SMALL,
            )

        # ── Legend (top-right corner) ─────────────────────────────────────────
        for i, (label, colour) in enumerate(
            [("Completed", CLR_GREEN), ("Pending", CLR_PENDING)]
        ):
            lx = W - 160 + i * 80
            c.create_rectangle(lx, pad_t, lx + 12, pad_t + 12, fill=colour, outline="")
            c.create_text(lx + 16, pad_t + 6, text=label,
                          anchor="w", fill=CLR_TEXT, font=FONT_SMALL)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Extract Frame — run the full extraction pipeline
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ExtractFrame(tk.Frame):
    """
    Provides the Start Extraction button, a progress bar, and a scrollable
    results area that shows one card per processed file.

    The extraction pipeline runs entirely on a background thread so the UI
    stays responsive throughout. A _running flag prevents overlapping runs.

    On completion of each file, a result card is added to the results panel
    via self.after(0, …) to stay on the main thread. A per-file .log file is
    also written to the Log History folder tree.

    After a successful extraction:
      • Word / Excel / JSON exports are saved under the dated folder hierarchy
      • The PDF is moved on Box from the source folder to the Archive folder
      • The file entry in tracking_db.json is marked "Completed"
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app      = app
        self._running = False   # prevents starting a second extraction while one is active

        # ── Header row (title + start button) ────────────────────────────────
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

        # ── Indeterminate progress bar ────────────────────────────────────────
        # Starts spinning when extraction begins; stops when all files are done
        self._progress = ttk.Progressbar(self, orient="horizontal", mode="indeterminate")
        self._progress.pack(fill="x", padx=24, pady=(0, 6))

        # ── Current-operation status label ────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self._status_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(anchor="w", padx=24)

        # ── Scrollable results panel ──────────────────────────────────────────
        # One card is added per processed file. Previous cards are cleared when
        # a new extraction run starts.
        tk.Label(self, text="Results", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_BOLD).pack(anchor="w", padx=24, pady=(20, 4))
        container = tk.Frame(self, bg=CLR_BG)
        container.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Canvas + scrollbar for the cards area
        self._canvas = tk.Canvas(container, bg=CLR_BG, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # The actual frame that holds result cards lives inside the canvas
        self._results_frame = tk.Frame(self._canvas, bg=CLR_BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._results_frame, anchor="nw"
        )
        # Update scroll region whenever cards are added / removed
        self._results_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        # Keep the inner frame's width equal to the canvas width
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width),
        )

    # ── Silent log stub ───────────────────────────────────────────────────────
    def _log_write(self, msg: str):
        """
        No-op stub kept so that existing _do_extraction log calls do not raise
        AttributeError. The extraction log is now written to disk via
        write_extraction_log() instead of displayed in the UI.
        """
        pass

    # ── Result card builder ───────────────────────────────────────────────────
    def _add_result_card(self, fname: str, ref: str, status: str,
                         word: str, excel: str, json_: str):
        """
        Add a result card to the scrollable results panel.
        Must be called from the main thread (use self.after(0, …) from workers).

        fname  — PDF file name
        ref    — reference number (success) or error message (failure)
        status — "ok" for success, anything else for failure
        word / excel / json_ — relative output paths (empty on failure)
        """
        ok     = (status == "ok")
        colour = CLR_GREEN if ok else CLR_ORANGE

        # Card container
        card = tk.Frame(
            self._results_frame,
            bg=CLR_WHITE,
            highlightbackground="#E5E7EB",
            highlightthickness=1,
        )
        card.pack(fill="x", pady=4, ipady=8, ipadx=10)

        # Top row: filename (left) + status badge (right)
        top = tk.Frame(card, bg=CLR_WHITE)
        top.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(top, text=fname, bg=CLR_WHITE, fg=CLR_TEXT,
                 font=FONT_BOLD, anchor="w").pack(side="left")
        badge_text = "✅  Completed" if ok else "❌  Failed"
        tk.Label(top, text=badge_text, bg=colour, fg=CLR_WHITE,
                 font=FONT_SMALL, padx=8, pady=2).pack(side="right")

        if ok:
            # Show reference number and all three output file paths
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
        else:
            # Show the error message in red (ref param carries the error string)
            tk.Label(
                card, text=ref,
                bg=CLR_WHITE, fg="#C0392B",
                font=FONT_SMALL, anchor="w",
                wraplength=700, justify="left",
            ).pack(fill="x", padx=10, pady=(0, 4))

    # ── Extraction lifecycle ───────────────────────────────────────────────────
    def _start_extraction(self):
        """
        Called by the Start button. Guards against double-clicks via _running flag.
        Disables the button, starts the progress bar, clears old result cards,
        and launches the extraction on a background daemon thread.
        """
        if self._running:
            return   # ignore click if an extraction is already in progress
        self._running = True
        self._btn.config(state="disabled", text="  ⏳  Extracting…  ")
        self._progress.start(12)   # spin at 12 ms interval

        # Clear previous result cards
        for w in self._results_frame.winfo_children():
            w.destroy()

        threading.Thread(target=self._run_extraction, daemon=True).start()

    def _run_extraction(self):
        """
        Background thread wrapper around _do_extraction().
        Catches any uncaught exception from the pipeline and updates the status
        label. Always resets the button and progress bar on completion.
        """
        try:
            self._do_extraction()
        except Exception as exc:
            # Top-level error (e.g. Box auth failure, config missing)
            self.after(0, lambda e=exc: self._status_var.set(f"Error: {e}"))
        finally:
            self._running = False
            self.after(0, self._extraction_done)

    def _extraction_done(self):
        """Re-enable the button and stop the progress bar (called on main thread)."""
        self._progress.stop()
        self._btn.config(state="normal", text="  ▶  Start Extraction  ")

    # ── Main extraction pipeline ───────────────────────────────────────────────
    def _do_extraction(self):
        """
        Full extraction pipeline, runs on a background thread.

        Steps per PDF file:
          1. Download bytes from Box
          2. Decrypt (if password-protected) and extract text per page
          3. Parse all pages into a structured dict
          4. Export to Word, Excel, and JSON inside the dated folder hierarchy
          5. Move the PDF on Box from the source folder to the Archive folder
          6. Update tracking_db.json to mark the file Completed
          7. Write a per-file .log file to Log History/
          8. Add a result card to the UI (via self.after(0, …))

        Files that fail at any step are caught individually; a failure log and
        error card are generated, and the file remains Pending in the tracking DB.
        """
        # Dynamically import the extractor module at runtime so changes to
        # pdf_text_extractor.py take effect without restarting the UI.
        spec = importlib.util.spec_from_file_location(
            "pdf_text_extractor", BASE_DIR / "pdf_text_extractor.py"
        )
        extractor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extractor)

        self.after(0, lambda: self._status_var.set("Loading extractor module…"))

        # ── Read configuration ────────────────────────────────────────────────
        cfg               = extractor.load_config()
        password          = cfg.get("pdf_password", "")
        box_cfg           = cfg.get("box", {})
        folder_id         = box_cfg.get("folder_id", "0")           # Box source folder
        archive_folder_id = box_cfg.get("archive_folder_id", "")    # Box archive folder
        search_sub        = cfg.get("settings", {}).get("search_subfolders", True)

        # ── Authenticate with Box ─────────────────────────────────────────────
        self.after(0, lambda: self._status_var.set("Connecting to Box…"))
        client = extractor.get_box_client(box_cfg)

        # ── Find PDF files in the source folder ───────────────────────────────
        self.after(0, lambda: self._status_var.set("Scanning Box folder…"))
        pdf_files = extractor.find_pdf_files_on_box(client, folder_id, search_sub)

        if not pdf_files:
            # Nothing to extract — update status and return
            self.after(0, lambda: self._status_var.set("No PDFs found in source folder."))
            return

        db  = load_tracking()
        now = datetime.now()   # consistent timestamp for this entire extraction run

        # Ensure root output directories exist before writing any files
        for d in (extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # ── Process each PDF ──────────────────────────────────────────────────
        for box_file in pdf_files:
            fid   = box_file["id"]
            fname = box_file["name"]
            self.after(0, lambda n=fname: self._status_var.set(f"Processing: {n}"))

            try:
                # Step 1 — Download from Box (bytes held in memory, no disk temp file)
                pdf_bytes = extractor.download_pdf_bytes(client, fid, fname)

                # Step 2 — Decrypt (if needed) and extract text per page
                doc   = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
                pages = extractor.extract_text_by_page(doc)
                doc.close()   # release the fitz document as soon as pages are extracted

                # Step 3 — Parse all pages into a structured dict
                structured = extractor.build_structured_json(fname, pages)

                # Extract the Case Reference No to use as the output folder/file name.
                # Falls back to the PDF filename stem if the field is not found.
                ref_number = (
                    structured.get("report_summary", {})
                               .get("case_reference", "").strip()
                    or Path(fname).stem
                )

                # Step 4 — Export to dated folder hierarchy
                # Build the daily subfolder under each output root
                daily_word = build_extract_folder(extractor.WORD_OUT_DIR, now)
                daily_csv  = build_extract_folder(extractor.CSV_OUT_DIR,  now)
                daily_json = build_extract_folder(extractor.JSON_OUT_DIR, now)

                # Temporarily redirect the extractor's global output-dir constants
                # to the daily subfolders so resolve_output_path() writes there.
                # The finally block always restores the originals.
                extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = (
                    daily_word, daily_csv, daily_json
                )
                try:
                    word_path = extractor.export_to_word(fname, structured, ref_number, False)
                    csv_path  = extractor.export_to_csv( fname, structured, ref_number, False)
                    json_path = extractor.export_to_json(fname, structured, ref_number, False)
                finally:
                    # Restore original output-dir constants even if an export fails
                    extractor.WORD_OUT_DIR = BASE_DIR / "Word Extracts"
                    extractor.CSV_OUT_DIR  = BASE_DIR / "CSV Extracts"
                    extractor.JSON_OUT_DIR = BASE_DIR / "JSON File Extracts"

                # Step 5 — Move the PDF on Box to the Archive folder
                # Box's move() removes the file from the source folder in one API call.
                if archive_folder_id:
                    client.file(fid).move(
                        parent_folder=client.folder(archive_folder_id)
                    )

                # Step 6 — Mark the file as Completed in the tracking DB
                if fid not in db["files"]:
                    db["files"][fid] = {}
                db["files"][fid].update({
                    "name":           fname,
                    "status":         "Completed",
                    "last_extracted": now.isoformat(timespec="seconds"),
                    "ref_number":     ref_number,
                    "archived":       True,
                })

                # Step 7 — Write per-file extraction log to Log History/
                log_lines = [
                    "Background Check Report Automation — Extraction Log",
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
                    f"Box Archive Folder : {archive_folder_id or 'N/A'}",
                ]
                write_extraction_log(ref_number, now, "\n".join(log_lines))

                # Step 8 — Add a success result card on the main thread
                self.after(0, lambda f=fname, r=ref_number,
                                      w=str(word_path.relative_to(BASE_DIR)),
                                      x=str(csv_path.relative_to(BASE_DIR)),
                                      j=str(json_path.relative_to(BASE_DIR)):
                    self._add_result_card(f, r, "ok", w, x, j)
                )

            except Exception as exc:
                # ── Per-file failure handling ─────────────────────────────────
                # Keep the file as Pending so it can be retried
                if fid not in db["files"]:
                    db["files"][fid] = {"name": fname}
                db["files"][fid].setdefault("status", "Pending")

                # Write a failure log using the filename stem as the ref fallback
                ref_fallback = Path(fname).stem
                log_lines = [
                    "Background Check Report Automation — Extraction Log",
                    "=" * 60,
                    f"File       : {fname}",
                    f"Reference  : {ref_fallback}",
                    f"Started    : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Failed     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Status     : FAILED",
                    "",
                    "Error",
                    "-" * 40,
                    str(exc),
                ]
                write_extraction_log(ref_fallback, now, "\n".join(log_lines))

                # Add a failure result card on the main thread
                self.after(0, lambda f=fname, e=str(exc):
                    self._add_result_card(f, e, "error", "", "", "")
                )

        # ── Post-loop: persist tracking DB and update status ──────────────────
        save_tracking(db)
        self.app.db = db   # keep the app-level reference in sync
        self.after(0, lambda: self._status_var.set("Extraction complete."))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# AI Assistant — IBM Consulting Advantage ICA 1.0 (grounded lookup, hallucination guard).
# Ported from the web app (app.py) so both apps share
# identical anti-hallucination logic and routing.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

import re as _re_ai   # keep separate from any 're' already imported by the UI

# ─────────────────────────────────────────────────────────────────────────────
# Path constants for the AI helpers
# ─────────────────────────────────────────────────────────────────────────────
JSON_EXTRACTS_DIR = BASE_DIR / "JSON File Extracts"   # root for all .json outputs


def _name_matches(query_lower: str, stored_name: str) -> bool:
    """
    Match a free-text query against a stored name that may be in 'Last, First' format.
    Tries: substring match, token-set match (all query tokens present in name tokens),
    and reversed 'First Last' form of the stored name.
    """
    stored_lower = stored_name.lower()
    # Direct substring
    if query_lower in stored_lower:
        return True
    # Reverse 'Last, First Middle' → 'first middle last' and try again
    if "," in stored_lower:
        parts        = [p.strip() for p in stored_lower.split(",", 1)]
        reversed_name = f"{parts[1]} {parts[0]}".strip()
        if query_lower in reversed_name:
            return True
        # Also check all query tokens appear somewhere in the full name tokens
        name_tokens  = set(stored_lower.replace(",", " ").split())
        query_tokens = set(query_lower.split())
        if query_tokens and query_tokens.issubset(name_tokens):
            return True
    return False




# ─────────────────────────────────────────────────────────────────────────────
# Status emoji helpers
# ─────────────────────────────────────────────────────────────────────────────
_STATUS_EMOJI = {
    "cleared": "✅", "verified": "✅", "pass": "✅", "passed": "✅",
    "clear": "✅",
    "failed": "❌", "fail": "❌", "unverified": "❌", "adverse": "❌",
    "--": "⬜", "": "⬜",
}

def _status_icon(val: str) -> str:
    """Return an emoji for a status/result value."""
    v = (val or "").strip().lower()
    for key, icon in _STATUS_EMOJI.items():
        if key and key in v:
            return icon
    return "🔵"


# ─────────────────────────────────────────────────────────────────────────────
# skill_lookup_report — rich §MARKER§-free plain-text report lookup
# Deduplicates by case_reference (latest extracted_at wins per ref).
# Multiple different refs that match the query are ALL returned (up to 5).
# ─────────────────────────────────────────────────────────────────────────────
def skill_lookup_report(query: str) -> str:
    """Search extracted JSON reports by subject name or case reference."""
    if not query.strip():
        return "Please provide a name or reference number to search for."

    q_lower     = query.strip().lower()
    best_by_ref: dict = {}

    def _ingest(report: dict):
        s    = report.get("report_summary", {})
        name = s.get("subject_name", "")
        ref  = s.get("case_reference", "").strip()
        # Normalised dedup key — same ref different casing/whitespace = one record
        key  = ref.lower() or name.lower()
        if not _name_matches(q_lower, name) and q_lower not in key:
            return
        existing = best_by_ref.get(key)
        if existing is None:
            best_by_ref[key] = report
        else:
            # Keep whichever was extracted most recently
            if (report.get("extracted_at", "") or "") > (existing.get("extracted_at", "") or ""):
                best_by_ref[key] = report

    if JSON_EXTRACTS_DIR.exists():
        for jp in JSON_EXTRACTS_DIR.rglob("*.json"):
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    _ingest(json.load(fh))
            except Exception:
                continue

    if not best_by_ref:
        return f"No reports found matching '{query}'."

    # Sort by subject name for consistent ordering; all unique refs are shown
    matches = sorted(
        best_by_ref.values(),
        key=lambda r: r.get("report_summary", {}).get("subject_name", "").lower(),
    )

    OTHER_CHECK_ORDER = [
        "Adverse Media Check",
        "Global Sanctions",
        "Bankruptcy Check",
        "Financial/Credit Check",
        "Directorship Check",
        "Civil Litigation Check",
        "Professional License Qualification",
        "Social Media Screening",
    ]

    def _build_block(r: dict, index: int, total: int) -> str:
        s        = r.get("report_summary", {})
        subject  = s.get("subject_name", "--")
        ref_num  = s.get("case_reference", "--")
        delivery = s.get("delivery_date", "--")
        received = s.get("case_received", "")
        package  = s.get("package", "")
        overall  = s.get("overall_status", "--")

        lines = []
        if total > 1:
            lines.append(f"{'─'*50}")
            lines.append(f"Record {index} of {total}")
        lines.append(f"Subject: {subject} | Ref: {ref_num} | Delivery: {delivery}")
        if received and received.strip():
            lines.append(f"Case Received: {received}")
        if package and package.strip():
            lines.append(f"Package: {package}")
        lines.append(f"Overall Status: {_status_icon(overall)} {overall}")
        lines.append("")

        # Employment checks
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
                    ("Position",            "position_title"),
                    ("Address",             "company_address"),
                    ("Dates",               "dates_of_employment"),
                    ("Employment Status",   "status_of_employment"),
                    ("Reason for Exit",     "reason_for_exit"),
                    ("Eligible for Rehire", "eligible_for_rehire"),
                    ("Respondent",          "respondents_name"),
                    ("Respondent Title",    "respondents_title"),
                    ("Contact",             "contact_details"),
                    ("Verification Date",   "verification_date"),
                    ("Result",              "result"),
                    ("Notes",               "notes"),
                ]:
                    val = ec.get(key, "")
                    if val and str(val).strip():
                        lines.append(f"    {label}: {val}")
            lines.append("")

        # Professional reference checks
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
                    ("Result",           "result"),
                    ("Verifier Name",    "verifiers_name"),
                    ("Verifier Contact", "verifiers_contact"),
                    ("Notes",            "notes"),
                ]:
                    val = pr.get(key, "")
                    if val and str(val).strip() and str(val).strip() != "-":
                        lines.append(f"    {label}: {val}")
                for qa in pr.get("qa", []):
                    answer   = qa.get("answer", "").strip()
                    question = qa.get("question", "").strip()
                    if answer and question:
                        lines.append(f"    Q: {question}")
                        lines.append(f"    A: {answer}")
            lines.append("")

        # Database checks
        other_map = {
            oc.get("check_name", "").strip().lower(): oc
            for oc in r.get("other_checks", [])
        }
        lines.append("── Database Checks ──")
        for check_name in OTHER_CHECK_ORDER:
            oc       = next((v for k, v in other_map.items() if k == check_name.lower()), {})
            status   = oc.get("status", "--") if oc else "--"
            chk_icon = _status_icon(status)
            lines.append(f"  {chk_icon} {check_name}: {status}")
            result_val = oc.get("result", "") if oc else ""
            source_val = oc.get("source", "") if oc else ""
            if result_val and str(result_val).strip():
                lines.append(f"    Result: {result_val}")
            if source_val and str(source_val).strip():
                lines.append(f"    Source: {source_val}")

        return "\n".join(lines)

    total  = len(matches)
    blocks = [_build_block(r, i + 1, total) for i, r in enumerate(matches)]

    header = ""
    if total > 1:
        header = (
            f"Found {total} record(s) matching '{query}':\n"
            + "\n".join(
                f"  {i+1}. {r.get('report_summary',{}).get('subject_name','--')} "
                f"— Ref: {r.get('report_summary',{}).get('case_reference','--')}"
                for i, r in enumerate(matches)
            )
            + "\n\n"
        )
    return header + "\n\n".join(blocks)


# ─────────────────────────────────────────────────────────────────────────────
# get_log_history — plain-text log summary for Day/Week/Month/Year
# ─────────────────────────────────────────────────────────────────────────────
def get_log_history(period: str = "day") -> str:
    """Return a plain-text summary of extraction logs for the given period."""
    from datetime import timedelta
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
        try:
            log_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            log_date = today
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


# ─────────────────────────────────────────────────────────────────────────────
# trigger_extraction_for_chat — run extraction pipeline from the chat thread
# ─────────────────────────────────────────────────────────────────────────────
def trigger_extraction_for_chat() -> str:
    """Run the full extraction pipeline synchronously and return a text summary."""
    import importlib.util as _ilu

    spec      = _ilu.spec_from_file_location("pdf_text_extractor", BASE_DIR / "pdf_text_extractor.py")
    extractor = _ilu.module_from_spec(spec)
    spec.loader.exec_module(extractor)

    cfg               = extractor.load_config()
    password          = cfg.get("pdf_password", "")
    box_cfg           = cfg.get("box", {})
    folder_id         = box_cfg.get("folder_id", "0")
    archive_folder_id = box_cfg.get("archive_folder_id", "")
    search_sub        = cfg.get("settings", {}).get("search_subfolders", True)

    client    = extractor.get_box_client(box_cfg)
    pdf_files = extractor.find_pdf_files_on_box(client, folder_id, search_sub)

    if not pdf_files:
        return "No PDF files found in the Box source folder. Nothing to extract."

    db  = load_tracking()
    now = datetime.now()

    for d in (extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    results = []

    for box_file in pdf_files:
        fid   = box_file["id"]
        fname = box_file["name"]
        try:
            pdf_bytes  = extractor.download_pdf_bytes(client, fid, fname)
            doc        = extractor.open_and_decrypt_pdf(pdf_bytes, fname, password)
            pages      = extractor.extract_text_by_page(doc)
            doc.close()
            structured = extractor.build_structured_json(fname, pages)
            ref_number = (
                structured.get("report_summary", {}).get("case_reference", "").strip()
                or Path(fname).stem
            )
            daily_word = build_extract_folder(extractor.WORD_OUT_DIR, now)
            daily_csv  = build_extract_folder(extractor.CSV_OUT_DIR,  now)
            daily_json = build_extract_folder(extractor.JSON_OUT_DIR, now)
            extractor.WORD_OUT_DIR, extractor.CSV_OUT_DIR, extractor.JSON_OUT_DIR = (
                daily_word, daily_csv, daily_json
            )
            try:
                word_path = extractor.export_to_word(fname, structured, ref_number, False)
                csv_path  = extractor.export_to_csv( fname, structured, ref_number, False)
                json_path = extractor.export_to_json(fname, structured, ref_number, False)
            finally:
                extractor.WORD_OUT_DIR = BASE_DIR / "Word Extracts"
                extractor.CSV_OUT_DIR  = BASE_DIR / "CSV Extracts"
                extractor.JSON_OUT_DIR = BASE_DIR / "JSON File Extracts"

            if archive_folder_id:
                client.file(fid).move(parent_folder=client.folder(archive_folder_id))

            if fid not in db["files"]:
                db["files"][fid] = {}
            db["files"][fid].update({
                "name": fname, "status": "Completed",
                "last_extracted": now.isoformat(timespec="seconds"),
                "ref_number": ref_number, "archived": True,
            })
            log_lines = [
                "Background Check Report Automation — Extraction Log",
                "=" * 60,
                f"File       : {fname}",
                f"Reference  : {ref_number}",
                f"Started    : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Completed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status     : Completed",
                "", "Outputs", "-" * 40,
                f"Word  : {word_path}",
                f"Excel : {csv_path}",
                f"JSON  : {json_path}",
            ]
            log_path = write_extraction_log(ref_number, now, "\n".join(log_lines))
            results.append({
                "status": "ok",
                "fname":  fname,
                "ref":    ref_number,
                "word":   str(word_path),
                "excel":  str(csv_path),
                "json":   str(json_path),
            })
        except Exception as exc:
            ref_fallback = Path(fname).stem
            if fid not in db["files"]:
                db["files"][fid] = {"name": fname}
            db["files"][fid].setdefault("status", "Pending")
            log_lines = [
                "Background Check Report Automation — Extraction Log",
                "=" * 60,
                f"File    : {fname}",
                f"Started : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Failed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Status  : FAILED",
                "", "Error", "-" * 40,
                str(exc),
            ]
            log_path = write_extraction_log(ref_fallback, now, "\n".join(log_lines))
            results.append({
                "status": "error",
                "fname":  fname,
                "error":  str(exc)[:300],
            })

    save_tracking(db)
    items = results
    completed = sum(1 for i in items if i.get("status") == "ok")
    failed    = sum(1 for i in items if i.get("status") == "error")
    header    = (
        f"Extraction started at {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Files found: {len(pdf_files)}\n"
        f"Completed: {completed}  |  Failed: {failed}"
    )
    payload = json.dumps({"header": header, "items": items})
    return f"\u00a7LINKS\u00a7{payload}\u00a7LINKS\u00a7"


# ─────────────────────────────────────────────────────────────────────────────
# LLM integration — IBM Consulting Advantage (ICA) 1.0
# Uses identical system prompt (Rules 1–8 anti-hallucination).
# Uses urllib so no extra dependencies are needed.
# ─────────────────────────────────────────────────────────────────────────────
_AI_SYSTEM_PROMPT = (
    "You are Detective Conan, an AI assistant for the Background Check Report Automation system. "
    "You help HR staff manage background check reports processed through IBM Box.\n\n"
    "You can help with:\n"
    "- Answering questions about background check reports (employment, criminal, identity checks)\n"
    "- Explaining file status, extraction results, and logs\n"
    "- Guiding users to use commands: 'scan box', 'run extraction', 'file status', "
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
    """Return the full config.json dict."""
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def ica_chat(history: list[dict], user_message: str) -> str:
    """
    Send a conversation turn to IBM Consulting Advantage (ICA) 1.0 and return the reply.
    Uses urllib — no extra SDK required.

    ICA requires the FULL browser cookie string (not just ica_core_auth_proxy) because
    Akamai bot-detection cookies (bm_sz, bm_sv, _abck, ak_bmsc) are also validated.

    Credentials in config.json → ica:
      full_cookie — entire cookie header copied from DevTools → Request Headers → cookie
      team_id     — ICA team UUID
      team_name   — ICA team name (URL-encoded, e.g. Synapxe%20ODC)
      chat_id     — ICA chat thread UUID
      base_url    — https://servicesessentials.ibm.com/curatorai/services/chat/new-chat
    """
    import urllib.request
    import urllib.error

    cfg          = _load_ai_config()
    ic           = cfg.get("ica", {})
    cookie       = ic.get("full_cookie", "")
    team_id      = ic.get("team_id", "")
    team_name    = ic.get("team_name", "")
    assistant_id = ic.get("assistant_id", "")
    chat_id      = ic.get("chat_id", "")
    base_url  = ic.get("base_url", "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat").rstrip("/")

    if not cookie:
        raise ValueError("ICA full_cookie not configured in config.json → ica.full_cookie")
    if not team_id:
        raise ValueError("ICA team_id not configured in config.json → ica.team_id")
    if not chat_id:
        raise ValueError("ICA chat_id not configured in config.json → ica.chat_id")

    # ICA payload confirmed from browser DevTools Payload tab
    url = f"{base_url}/chats/{chat_id}/entries"
    payload = json.dumps({
        "chatId": chat_id,
        "type":   "PROMPT",
        "content": {
            "prompt":               user_message,
            "promptId":             "",
            "promptUuid":           "",
            "isIncludedInContext":  True,
            "sensitiveInformation": {"hasSensitiveInformation": False},
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "cookie":        cookie,
            "teamid":        team_id,
            "teamname":      team_name,
            "Content-Type":  "application/json",
            "Accept":        "application/json, text/plain, */*",
            "Origin":        "https://servicesessentials.ibm.com",
            "Referer":       f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
            "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            echo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ICA {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")

    # POST returns the prompt echo — poll GET /entries until ANSWER arrives
    import time
    entry_id = echo.get("_id", "")
    base_headers = {
        "cookie":        cookie,
        "teamid":        team_id,
        "teamname":      team_name,
        "Accept":        "application/json, text/plain, */*",
        "Origin":        "https://servicesessentials.ibm.com",
        "Referer":       f"https://servicesessentials.ibm.com/curatorai/apps/ui/new-chat/{chat_id}",
        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }
    # Poll GET /chats/{chat_id}/entries — find ANSWER whose promptEntryId matches our prompt _id
    poll_url = f"{base_url}/chats/{chat_id}/entries"
    for _ in range(30):  # up to 30 × 2s = 60s
        time.sleep(2)
        poll_req = urllib.request.Request(poll_url, headers=base_headers, method="GET")
        try:
            with urllib.request.urlopen(poll_req, timeout=30) as poll_resp:
                data = json.loads(poll_resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            continue
        entries = data if isinstance(data, list) else data.get("data", data.get("entries", []))
        answers = [e for e in entries if e.get("type") == "ANSWER"]
        if answers:
            return str(answers[-1].get("content", {}).get("answer", "")).strip() or "(No response from ICA)"
    return "(ICA did not respond in time)"


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination guard — identical to web app
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
    r"education\s*:\s*\n",
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
    """Strip assistant turns that contain hallucinated report data."""
    clean = []
    for turn in history:
        if turn.get("role") == "assistant" and _is_hallucinated_reply(turn.get("content", "")):
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
# trigger_scan_for_chat — run the Local Folder scan synchronously and return
# a text summary (mirrors V2).
# ─────────────────────────────────────────────────────────────────────────────
def trigger_scan_for_chat() -> str:
    """Run the Local Folder scan synchronously and return a text summary."""
    try:
        local_folder     = _local_folder()
        extracted_folder = _extracted_folder()
        archive_folder   = _archive_folder()
        db               = load_tracking()
        found            = 0

        for pdf_path in local_folder.rglob("*.pdf"):
            try:
                pdf_path.relative_to(extracted_folder); continue
            except ValueError:
                pass
            try:
                pdf_path.relative_to(archive_folder); continue
            except ValueError:
                pass
            rel_key  = str(pdf_path.relative_to(local_folder))
            existing = db.get("files", {}).get(rel_key, {})
            db["files"][rel_key] = {
                "name":           pdf_path.name,
                "status":         "Pending",
                "last_extracted": existing.get("last_extracted"),
                "ref_number":     existing.get("ref_number"),
                "local_path":     str(pdf_path),
            }
            found += 1

        # Purge stale entries
        stale = []
        for rel_key, info in db.get("files", {}).items():
            src  = Path(info.get("local_path", local_folder / rel_key))
            arch = Path(info.get("archive_path", ""))
            if not src.exists() and not arch.exists():
                stale.append(rel_key)
        for rel_key in stale:
            del db["files"][rel_key]

        save_tracking(db)

        files     = db.get("files", {})
        pending   = sum(1 for f in files.values() if f.get("status") == "Pending")
        completed = sum(1 for f in files.values() if f.get("status") == "Completed")
        lines = [f"🔍 Scan complete — **{found}** PDF(s) found in Local Folder.\n"]
        lines.append(f"**Total:** {len(files)}   |   ✅ Completed: {completed}   |   🕐 Pending: {pending}\n")
        if files:
            lines.append("")
            for rel_key, info in files.items():
                status = info.get("status", "Pending")
                icon   = "✅" if status == "Completed" else "🕐"
                ref    = info.get("ref_number") or "--"
                lines.append(f"  {icon}  {info.get('name', rel_key)}  (Ref: {ref})")
        return "\n".join(lines)
    except Exception as exc:
        return f"⚠ Scan failed: {str(exc)[:200]}"


# ─────────────────────────────────────────────────────────────────────────────
# route_chat_message — full 10-step priority routing (mirrors web app api_chat)
# Called from the ChatFrame background thread; returns a plain-text reply string.
# ─────────────────────────────────────────────────────────────────────────────
def route_chat_message(message: str, history: list[dict]) -> str:
    """
    Route a user message through the same priority chain as the web app:
      1. Scan keywords   → trigger_scan_for_chat()
      2. Extraction      → trigger_extraction_for_chat()
      3. File status     → load_tracking() counts
      4. Log keywords    → get_log_history()
      5. Pending-download context check
      6. Report download / generate (not applicable in desktop — redirect)
      7. Lookup verb patterns → skill_lookup_report()
      8. Bare check-name guard
      9. Bare name/ref guard → skill_lookup_report()
     10. Affirmative follow-up
     11. LLM (ICA 1.0) with hallucination guard
    """
    history = _sanitize_history(history)
    lower   = message.lower()

    # ── 1. Scan ───────────────────────────────────────────────────────────────
    if any(kw in lower for kw in ("scan box", "scan folder", "check box", "scan", "rescan")):
        return trigger_scan_for_chat()

    # ── 2. Extraction ─────────────────────────────────────────────────────────
    if any(kw in lower for kw in (
        "run extract", "start extract", "extract now", "extract files",
        "run pipeline", "extract", "process files", "process reports",
        "generate report", "generate reports", "create report", "create reports",
        "run report", "run reports", "produce report", "produce reports",
    )):
        return trigger_extraction_for_chat()

    # ── 3. File status ────────────────────────────────────────────────────────
    if any(kw in lower for kw in (
        "file status", "how many files", "pending files", "files pending",
        "files completed", "file count",
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

    # ── 4. Logs ───────────────────────────────────────────────────────────────
    if any(kw in lower for kw in (
        "show logs", "view logs", "logs today", "logs this week",
        "logs this month", "logs this year", "extraction log",
        "extraction history", "show log", "view log", "logs",
    )):
        period = "year" if "year" in lower else "month" if "month" in lower else "week" if "week" in lower else "day"
        return get_log_history(period)

    # ── 5. Pending-download context check ─────────────────────────────────────
    _PENDING_MARKERS = (
        "which report would you like",
        "please specify a name",
        "no report files found for",
        "if the report hasn't been extracted",
    )
    _last_bot = next(
        (t.get("content", "") for t in reversed(history) if t.get("role") == "assistant"),
        ""
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

    # ── 6. Report download — redirect to local files ──────────────────────────
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
            return (
                f"The extracted files for **{_rq}** are saved locally in:\n"
                f"  • Word Extracts/\n"
                f"  • CSV Extracts/\n"
                f"  • JSON File Extracts/\n\n"
                f"Navigate to those folders or use 'look up {_rq}' to see the report data here."
            )

    # ── 7. Lookup verb patterns ───────────────────────────────────────────────
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
            query = _re_ai.sub(r"\s*(?:please|now|thanks?|report|record|details?)\s*$", "", query, flags=_re_ai.IGNORECASE).strip()
            if query and len(query) >= 3:
                result = skill_lookup_report(query)
                if not result.startswith("No reports found"):
                    return result
                return (
                    f"No records found matching **'{query}'** in our extracted reports.\n"
                    "Please check the name or reference number and try again, "
                    "or run an extraction if the report has not been processed yet."
                )

    # ── 8. Bare check-name guard ──────────────────────────────────────────────
    _CHECK_NAME_RE = _re_ai.compile(
        r"^(?:adverse\s+media|global\s+sanctions|bankruptcy|financial(?:/credit)?|"
        r"credit|directorship|civil\s+litigation|professional\s+licen[sc]e|"
        r"social\s+media)\s*(?:check|screening|verification)?$",
        _re_ai.IGNORECASE,
    )
    if _CHECK_NAME_RE.match(lower.strip()):
        return (
            f"Which person's **{message.strip()}** result would you like to see?\n"
            f"Please use: **'look up [name]'** or **'{message.strip()} for [name]'**"
        )

    # ── 9. Bare name/ref guard ────────────────────────────────────────────────
    _PREFIX_STRIP = _re_ai.compile(
        r"^(?:overall\s+status|status|report|details?|info(?:rmation)?)\s+(?:(?:for|of|on|about)\s+)?",
        _re_ai.IGNORECASE,
    )
    _reserved = {
        "scan", "rescan", "extract", "status", "logs", "log", "help",
        "hello", "hi", "hey", "yes", "no", "ok", "okay", "sure",
        "thanks", "thank", "clear", "quit", "exit",
        "insights", "dashboard", "home", "check", "check box",
        "file insights", "show file insights", "show insights",
        "view insights", "show dashboard", "view dashboard",
        "show status", "show file status", "view file status",
        "overall status", "what is the overall status",
        "pipeline", "run pipeline", "process",
        "generate report", "generate reports", "create report", "create reports",
        "run report", "run reports", "produce report", "produce reports",
        "start extraction", "run extraction", "start pipeline",
    }
    _bare = _PREFIX_STRIP.sub("", message.strip()).strip()
    _bare_lower = _bare.lower()
    if (
        len(_bare) >= 3
        and len(_bare) <= 60
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

    # ── 10. Affirmative follow-up ─────────────────────────────────────────────
    _affirmative = {
        "yes", "yeah", "yep", "sure", "show", "view", "show me", "show details",
        "view details", "full report", "full details", "show report", "view report",
        "show full", "view full", "more details", "more info", "see more",
        "overall status", "status",
    }
    if lower.strip() in _affirmative or lower.strip().startswith(("yes ", "show ", "view ")):
        for turn in reversed(history):
            if turn.get("role") == "assistant":
                prev = turn.get("content", "")
                subj_match = _re_ai.search(r"Subject:\s*([^\|]+)", prev)
                if subj_match:
                    return skill_lookup_report(subj_match.group(1).strip())
                break

    # ── 11. LLM (ICA 1.0) with grounded context + hallucination guard ──────────
    cfg = _load_ai_config()

    # Build grounded context anchor from history if a prior lookup result exists
    grounded_context = None
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            prev = turn.get("content", "")
            if _re_ai.search(r"Subject:\s*[^\|]+\|", prev):
                grounded_context = prev
                break

    # ── Absolute pre-LLM guard ────────────────────────────────────────────────
    _REPORT_INQUIRY_RE = _re_ai.compile(
        r"(?:yes|yeah|yep|sure|show|view|full\s+report|full\s+details?|"
        r"more\s+(?:details?|info)|see\s+more|tell\s+me\s+more|"
        r"what\s+(?:is|are|was|were)|who\s+is|background\s+check|"
        r"criminal\s+record|employment\s+(?:history|verification)|"
        r"identity\s+verif|education|reference\s+check|"
        r"report\s+(?:for|of|on|details?)|check\s+result)",
        _re_ai.IGNORECASE,
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
        return [
            {
                "role": "system",
                "content": (
                    "The following is the ONLY data you are permitted to use when "
                    "answering questions about this person. Do not add, infer, or "
                    "invent anything beyond what is listed here.\n\n"
                    "EXTRACTED RECORD:\n" + grounded_context
                ),
            }
        ] + hist

    _HALLUCINATION_BLOCKED = (
        "I can only answer from our extracted records. "
        "Please use 'look up [name or reference]' to retrieve the report first, "
        "then ask your question."
    )

    # ICA 1.0
    ica_ready = (
        cfg.get("ica", {}).get("full_cookie", "") != ""
        and cfg.get("ica", {}).get("team_id", "") != ""
        and cfg.get("ica", {}).get("chat_id", "") != ""
    )
    if ica_ready:
        try:
            reply = ica_chat(_build_anchored_history(history), message)
            if _is_hallucinated_reply(reply):
                return _HALLUCINATION_BLOCKED
            return reply
        except Exception as exc:
            return f"⚠ ICA error: {str(exc)[:200]}"

    # Local fallback — no LLM configured
    return (
        "Hi! I'm Detective Conan. I can help with:\n"
        "• 'look up [name]'      — search extracted reports\n"
        "• 'extract'             — run the extraction pipeline\n"
        "• 'file status'         — show Pending / Completed counts\n"
        "• 'logs this week'      — view extraction log history\n\n"
        "Configure ICA credentials in config.json to enable full AI responses."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Chat Frame — AI Assistant (ICA 1.0, grounded, anti-hallucination)
# ══════════════════════════════════════════════════════════════════════════════
class ChatFrame(tk.Frame):
    """
    Conversational AI assistant.

    Uses route_chat_message() for all routing — identical logic to the web app:
      • report lookup (grounded, §MARKER§-free plain-text)
      • extraction pipeline trigger
      • log history
      • file status counts
      • hallucination guard (pre-LLM and post-LLM)
      • IBM Consulting Advantage (ICA 1.0) → local fallback

    Conversation history is kept in memory for the session and cleared on 'Clear'.
    Each AI call runs on a background daemon thread.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=CLR_BG)
        self.app      = app
        self._history: list[dict] = []
        self._busy    = False

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CLR_BG)
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(hdr, text="AI Assistant", bg=CLR_BG,
                 fg=CLR_TEXT, font=FONT_TITLE).pack(side="left")

        tk.Button(
            hdr, text="🗑  Clear Chat",
            bg=CLR_ACCENT, fg=CLR_WHITE,
            font=FONT_SMALL, relief="flat", cursor="hand2",
            padx=8, pady=4,
            command=self._clear_chat,
        ).pack(side="right")

        # Model badge — shows active LLM
        self._model_var = tk.StringVar(value="Model: —")
        tk.Label(hdr, textvariable=self._model_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(side="right", padx=12)

        # ── Chat display ──────────────────────────────────────────────────────
        chat_outer = tk.Frame(self, bg=CLR_BG)
        chat_outer.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        self._chat_display = tk.Text(
            chat_outer,
            bg=CLR_WHITE, fg=CLR_TEXT,
            font=("Segoe UI", 10),
            relief="flat",
            wrap="word",
            state="disabled",
            highlightbackground="#E5E7EB",
            highlightthickness=1,
            padx=12, pady=8,
            cursor="arrow",
        )
        chat_sb = ttk.Scrollbar(chat_outer, orient="vertical",
                                command=self._chat_display.yview)
        self._chat_display.configure(yscrollcommand=chat_sb.set)
        self._chat_display.pack(side="left", fill="both", expand=True)
        chat_sb.pack(side="right", fill="y")

        # Text tags for message styling
        self._chat_display.tag_configure(
            "user",        foreground="#1F3864", font=("Segoe UI", 10, "bold"))
        self._chat_display.tag_configure(
            "assistant",   foreground="#22863A", font=("Segoe UI", 10))
        self._chat_display.tag_configure(
            "asst_bold",   foreground="#22863A", font=("Segoe UI", 10, "bold"))
        self._chat_display.tag_configure(
            "asst_italic", foreground="#22863A", font=("Segoe UI", 10, "italic"))
        self._chat_display.tag_configure(
            "asst_hr",     foreground="#AAAAAA", font=("Segoe UI", 9))
        self._chat_display.tag_configure(
            "system",      foreground=CLR_MUTED,  font=("Segoe UI", 9, "italic"))
        self._chat_display.tag_configure(
            "error",       foreground=CLR_ORANGE, font=("Segoe UI", 9, "italic"))

        # ── Input row ─────────────────────────────────────────────────────────
        input_frame = tk.Frame(self, bg=CLR_BG)
        input_frame.pack(fill="x", padx=24, pady=(0, 16))

        self._input_var = tk.StringVar()
        self._input_box = tk.Entry(
            input_frame,
            textvariable=self._input_var,
            font=("Segoe UI", 10),
            relief="flat",
            bg=CLR_WHITE,
            fg=CLR_TEXT,
            highlightbackground="#E5E7EB",
            highlightthickness=1,
        )
        self._input_box.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._input_box.bind("<Return>", lambda e: self._send())

        self._send_btn = tk.Button(
            input_frame,
            text="  Send  ",
            bg=CLR_GREEN, fg=CLR_WHITE,
            font=FONT_BOLD, relief="flat", cursor="hand2",
            padx=10, pady=6,
            command=self._send,
        )
        self._send_btn.pack(side="right")

        # Typing indicator
        self._typing_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._typing_var,
                 bg=CLR_BG, fg=CLR_MUTED, font=FONT_SMALL).pack(
                     anchor="w", padx=24, pady=(0, 4))

    def on_show(self):
        """Called when this frame becomes active. Show welcome message on first open."""
        if not self._history:
            self._append_message("system",
                "👋  Hello! I'm Detective Conan, your AI Assistant.\n\n"
                "I can help you with:\n\n"
                "📋  Check Results\n"
                "  • 'look up Jose Manalo'\n"
                "  • 'show me the report for Manalo'\n"
                "  • 'what is the overall status of RN-123456?'\n"
                "  • 'Social Media Screening for Manalo'\n"
                "  • 'Adverse Media Check for RN-123456'\n\n"
                "⚙️  Extraction\n"
                "  • 'run extraction'\n"
                "  • 'extract files'\n\n"
                "📜  Log History\n"
                "  • 'logs this week'\n"
                "  • 'show this month\\'s logs'\n\n"
                "📊  Status\n"
                "  • 'file status'\n"
                "  • 'how many files are pending?'\n"
            )
        # Update the model badge
        try:
            cfg = _load_ai_config()
            ic  = cfg.get("ica", {})
            ica_ok = (
                ic.get("full_cookie", "") != ""
                and ic.get("team_id", "") != ""
                and ic.get("chat_id", "") != ""
            )
            if ica_ok:
                self._model_var.set("Model: IBM Consulting Advantage")
            else:
                self._model_var.set("AI: add ICA credentials in config.json")
        except Exception:
            self._model_var.set("AI: config error")
        self._input_box.focus_set()

    def _insert_markdown(self, text: str):
        """
        Insert assistant text with basic markdown rendering into _chat_display.
        Handles **bold**, *italic*, and --- horizontal rules.
        Widget must already be in state="normal" before calling.
        """
        import re as _re_md
        w = self._chat_display
        # Process line by line
        for line in text.split("\n"):
            # Horizontal rule
            if _re_md.match(r"^\s*---+\s*$", line):
                w.insert("end", "─" * 48 + "\n", "asst_hr")
                continue
            # Bold + italic inline spans
            parts = _re_md.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    w.insert("end", part[2:-2], "asst_bold")
                elif part.startswith("*") and part.endswith("*"):
                    w.insert("end", part[1:-1], "asst_italic")
                else:
                    w.insert("end", part, "assistant")
            w.insert("end", "\n", "assistant")

    def _append_message(self, role: str, text: str):
        """Append a styled message to the chat display. Must be called on the main thread."""
        self._chat_display.config(state="normal")
        if role == "user":
            self._chat_display.insert("end", "\nYou:  ", "user")
            self._chat_display.insert("end", text + "\n", "user")
        elif role == "assistant":
            self._chat_display.insert("end", "\nAssistant:  ", "assistant")
            self._insert_markdown(text)
        elif role == "system":
            self._chat_display.insert("end", text + "\n", "system")
        else:
            self._chat_display.insert("end", f"\n⚠ {text}\n", "error")
        self._chat_display.config(state="disabled")
        self._chat_display.see("end")

    def _append_links(self, payload_json: str):
        """
        Render extraction results with clickable file hyperlinks in the chat display.
        payload_json is the JSON string produced by trigger_extraction_for_chat().
        Always re-enables the input widgets in a finally block so they can never
        stay locked even if an unexpected exception occurs during rendering.
        """
        import os
        try:
            try:
                payload = json.loads(payload_json)
            except Exception:
                self._append_message("assistant", payload_json)
                return

            w = self._chat_display
            w.config(state="normal")

            # ── Header ────────────────────────────────────────────────────────
            w.insert("end", "\nAssistant:  ", "assistant")
            w.insert("end", payload.get("header", "") + "\n\n", "assistant")

            for idx, item in enumerate(payload.get("items", [])):
                if item.get("status") == "ok":
                    ref   = item.get("ref",   "")
                    fname = item.get("fname", "")
                    w.insert("end", f"  ✅  {fname}  —  Ref: {ref}\n", "assistant")
                    for label, key in [("📄 Word", "word"), ("📊 Excel", "excel"), ("🗂 JSON", "json")]:
                        path_str = item.get(key, "")
                        if path_str and Path(path_str).exists():
                            tag = f"link_{idx}_{key}"
                            w.insert("end", f"     {label}:  ", "assistant")
                            w.insert("end", Path(path_str).name, tag)
                            w.insert("end", "\n", "assistant")
                            w.tag_configure(tag, foreground="#2E75B6",
                                            font=("Segoe UI", 10, "underline"),
                                            cursor="hand2")
                            w.tag_bind(tag, "<Button-1>",
                                       lambda e, p=path_str: os.startfile(p))
                    w.insert("end", "\n", "assistant")
                else:
                    fname = item.get("fname", "")
                    error = item.get("error", "")
                    w.insert("end", f"  ❌  {fname}\n     Error: {error}\n\n", "error")

            w.config(state="disabled")
            w.see("end")
        finally:
            # Always re-enable — no exception can leave the chat locked
            self._busy = False
            self._input_box.config(state="normal")
            self._send_btn.config(state="normal")
            self._input_box.focus_set()

    def _clear_chat(self):
        self._history = []
        self._chat_display.config(state="normal")
        self._chat_display.delete("1.0", "end")
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
        """Background thread: route message and post reply to main thread."""
        try:
            reply = route_chat_message(user_message, list(self._history))
            # Persist history (un-enriched message)
            self._history.append({"role": "user",      "content": user_message})
            self._history.append({"role": "assistant", "content": reply})
            # Cap history at 40 messages
            if len(self._history) > 40:
                self._history = self._history[-40:]
            self.after(0, lambda r=reply: self._on_reply(r))
        except Exception as exc:
            self.after(0, lambda e=exc: self._on_error(str(e)))

    def _on_reply(self, reply: str):
        self._typing_var.set("")
        _LINKS_START = "\u00a7LINKS\u00a7"
        _LINKS_END   = "\u00a7LINKS\u00a7"
        if reply.startswith(_LINKS_START) and reply.endswith(_LINKS_END):
            inner = reply[len(_LINKS_START):-len(_LINKS_END)]
            self._append_links(inner)
        else:
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
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = PDFExtractorApp()
    app.mainloop()
