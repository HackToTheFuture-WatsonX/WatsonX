# Background Check Report Automation — V1

Desktop application for processing background check PDF reports from IBM Box.

---

## Screens

| Screen | Purpose |
|--------|---------|
| **Home** | Landing page — shortcut cards for each step |
| **Check Box** | Scan Box folder for PDFs and register them as Pending |
| **Extract Files** | Run extraction pipeline — decrypt, parse, export to Word / Excel / JSON |
| **Chat with AI Assistant** | Conversational AI powered by IBM Consulting Advantage (ICA 1.0) |

---

## Process Flow

```
Box (folder_id)
      │
      ▼  Check Box — scan for PDFs
Tracking DB (Pending files)
      │
      ▼  Extract Files
Word Extracts/
CSV Extracts/
JSON File Extracts/   ← AI Assistant reads from here
```

### Step-by-step

1. **Check Box** — Click "Scan Box Folder" to scan your Box folder and register PDFs as Pending.
2. **Extract Files** — Click "Start Extraction" to process all Pending PDFs:
   - Download each PDF from Box into memory
   - Decrypt using `pdf_password`
   - Parse and export Word / Excel / JSON into the app folder
   - Mark each file Completed
3. **Chat with AI Assistant** — Ask questions about reports or run commands.

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
    "client_id":     "your_box_client_id",
    "client_secret": "your_box_client_secret",
    "access_token":  "your_developer_token",
    "folder_id":     "your_box_folder_id"
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
| `box.folder_id` | Box folder to scan for PDFs |
| `box.access_token` | Box Developer Token (expires every 60 min) |
| `ica.*` | IBM Consulting Advantage credentials — use the ICA Cookie Parser tool to generate |

### 3. Launch

Double-click `Launch.vbs`, or run:

```bash
python pdf_extractor_ui.py
```

---

## Folder Structure

```
PDF Extractor/
├── pdf_extractor_ui.py        Main UI — run this
├── pdf_text_extractor.py      Core extraction engine
├── config.json                Credentials and settings
├── tracking_db.json           Auto-created — per-file Pending/Completed state
├── Launch.vbs                 Double-click to launch without a console window
├── requirements.txt           Python dependencies
├── Word Extracts/             Exported .docx files
├── CSV Extracts/              Exported .xlsx files
├── JSON File Extracts/        Exported .json files
└── Log History/               Per-file extraction logs
```

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
| `scan` | Scan Local Folder for PDFs |
| `extract` | Run extraction pipeline on all Pending files |
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

- Box Developer Tokens expire after **60 minutes**. Refresh `box.access_token` in `config.json` before scanning or extracting.
- All extraction logs are written to `Log History/YYYY/MMM_YYYY/Week_NN/YYYY-MM-DD/`.
- V2 is recommended for new deployments — it adds sync, auto-scan, View Extracted Files, and a richer AI chat flow.
