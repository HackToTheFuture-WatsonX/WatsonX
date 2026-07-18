# Background Check Report Automation — V2

Desktop application for processing background check PDF reports from IBM Box.

---

## What's New in V2

| Feature | V1 | V2 |
|---------|----|----|
| PDF source | Downloaded from Box during extraction | **Synced to Local Folder first** |
| Scan target | Box folder (via API) | **Local Folder** (no API needed for scan) |
| Output location | App root — `Word Extracts/` etc. | **`Local Folder/Extracted/`** (dated hierarchy) |
| Post-extraction | None | **Uploads Word / Excel / JSON to Box** `output_folder_id` |
| AI source | App-root JSON files | **`Local Folder/Extracted/JSON File Extracts/`** |
| Sync | None | **Sync Box to Local** — manual button + optional auto-schedule |
| Auto-scan | None | **Scan runs automatically after every sync** |

---

## Screens

| Screen | Purpose |
|--------|---------|
| **Home** | Landing page — shortcut cards for each step |
| **Scan Local Folder** | Detect PDFs in Local Folder and register them as Pending |
| **Sync Box to Local** | Download PDFs from Box into Local Folder (manual or auto-schedule) |
| **Extract Files** | Run extraction pipeline — decrypt, parse, export, upload to Box |
| **View Extracted Files** | Browse all Word / Excel / JSON outputs grouped by reference |
| **Chat with AI Assistant** | Conversational AI powered by IBM Consulting Advantage (ICA 1.0) |

---

## Process Flow

```
Box (folder_id)
      │
      ▼  Sync Box to Local
Local Folder/
  ├── report1.pdf
  ├── report2.pdf          ← Pending after Scan
  └── Extracted/
        ├── Word Extracts/
        │     └── 2026/Jul_2026_Extracts/Week_28/2026-07-10/RN-123456/
        ├── CSV Extracts/
        └── JSON File Extracts/  ← AI Assistant reads from here
                │
                ▼  Extract Files (upload)
      Box (output_folder_id)
```

### Step-by-step

1. **Sync Box to Local** — Click "Sync Now" to download all PDFs from Box into `Local Folder/`.
   Scan runs automatically after sync completes — no extra click needed.
2. **Extract Files** — Click "Start Extraction" to process all Pending PDFs:
   - Decrypt using `pdf_password`
   - Parse and export Word / Excel / JSON into `Local Folder/Extracted/`
   - Upload all 3 output files to Box `output_folder_id`
   - Mark each file Completed
3. **View Extracted Files** — Browse all output files grouped by type and reference number. Click any filename to open it.
4. **Chat with AI Assistant** — Ask questions about reports, run commands, or open files by name.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `config.json`

```json
{
  "pdf_password": "your_pdf_password",
  "box": {
    "client_id":        "your_box_client_id",
    "client_secret":    "your_box_client_secret",
    "access_token":     "your_developer_token",
    "folder_id":        "398448580241",
    "output_folder_id": "your_output_box_folder_id"
  },
  "sync": {
    "auto_sync_enabled": false,
    "auto_sync_interval_minutes": 30
  },
  "ica": {
    "full_cookie":   "paste_full_cookie_from_devtools",
    "team_id":       "your_ica_team_id",
    "team_name":     "Your%20Team",
    "assistant_id":  "your_ica_assistant_id",
    "chat_id":       "your_ica_chat_id",
    "base_url":      "https://servicesessentials.ibm.com/curatorai/services/chat/new-chat"
  }
}
```

Key fields:

| Field | Description |
|-------|-------------|
| `pdf_password` | Password to decrypt the PDF reports |
| `box.folder_id` | Source Box folder to sync PDFs **from** |
| `box.output_folder_id` | Box folder to upload extracted files **to** |
| `box.access_token` | Box Developer Token (expires every 60 min) |
| `sync.auto_sync_enabled` | Set to `true` to sync automatically on startup |
| `sync.auto_sync_interval_minutes` | How often to auto-sync (default `30`) |
| `ica.*` | IBM Consulting Advantage credentials — use the ICA Cookie Parser tool to generate |

### 3. Launch

Double-click `Launch.vbs`, or run:

```bash
python pdf_extractor_ui_v2.py
```

---

## Folder Structure

```
PDF Extractor V2/
├── pdf_extractor_ui_v2.py     Main UI — run this
├── pdf_text_extractor.py      Core extraction engine
├── config.json                Credentials and settings
├── tracking_db.json           Auto-created — per-file Pending/Completed state
├── Launch.vbs                 Double-click to launch without a console window
├── requirements.txt           Python dependencies
├── Local Folder/              PDFs synced from Box (git-ignored)
│   └── Extracted/             All extraction outputs
│       ├── Word Extracts/
│       ├── CSV Extracts/
│       └── JSON File Extracts/
└── Log History/               Per-file extraction logs
```

---

## Auto-Sync Configuration

```json
"sync": {
  "auto_sync_enabled": true,
  "auto_sync_interval_minutes": 30
}
```

- First sync fires **10 seconds** after app launch
- Re-schedules itself every `interval_minutes`
- Scan runs automatically after every sync
- Status shown on the Sync Box to Local screen

---

## ICA Credentials

The AI Assistant uses **IBM Consulting Advantage (ICA) 1.0**. To get your credentials:

1. Open the **ICA Cookie Parser** tool: `ICA Cookie Parser/ica_cookie_parser.html`
2. In your browser, open ICA and send any message
3. Open DevTools → Network → click the `entries` POST → Headers tab → copy all headers
4. Paste into the parser and click **Parse & Generate Config**
5. Copy the generated `"ica": { ... }` block into `config.json`

> ICA cookies expire periodically. Refresh them using the parser when the AI stops responding.

---

## AI Assistant — Chat Commands

| Command | What it does |
|---------|-------------|
| `sync` | Sync Box → Local Folder + auto-scan |
| `scan` | Scan Local Folder for PDFs |
| `extract` | Run extraction pipeline on all Pending files |
| `generate report` | List all available extracted reports |
| `generate report for [name]` | Find a specific report, ask for file type, open it |
| `look up [name or ref]` | Display report data in chat |
| `file status` | Show Pending / Completed counts |
| `logs this week` | View extraction log history |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `boxsdk` | Box API client |
| `PyMuPDF` | Open and decrypt PDFs |
| `python-docx` | Generate Word `.docx` exports |
| `openpyxl` | Generate Excel `.xlsx` exports |

---

## Notes

- Box Developer Tokens expire after **60 minutes**. Refresh `box.access_token` in `config.json` before syncing or uploading.
- `Local Folder/` and `Log History/` are excluded from git — they contain report data.
- All extraction logs are written to `Log History/YYYY/MMM_YYYY/Week_NN/YYYY-MM-DD/`.
