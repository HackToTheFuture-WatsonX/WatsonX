# Background Check Report Automation — Web App

Flask web application for processing background check PDF reports from IBM Box,
with an AI Assistant powered by **IBM Consulting Advantage (ICA) 1.0**.

---

## Screens

| URL | Screen | Purpose |
|-----|--------|---------|
| `/` | Home | Dashboard with stat cards and navigation |
| `/check` | Check Box Folder | Scan Box folder, view Pending files |
| `/extract` | Extract Files | Start pipeline, live progress, result cards |
| `/chat` | AI Assistant | Chat UI powered by IBM Consulting Advantage |

---

## Process Flow

```
Box (folder_id)
      │
      ▼  /check — scan Box folder
Tracking DB (Pending files)
      │
      ▼  /extract — extraction pipeline
Word Extracts/
CSV Extracts/
JSON File Extracts/   ← AI Assistant reads from here
```

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
    "folder_id":        "your_box_folder_id",
    "archive_folder_id":"your_archive_folder_id"
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

### 3. Run the server

```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## Folder Structure

```
WatsonX Challenge - Web/
├── app.py                     Flask server + ICA integration
├── config.json                All credentials (Box, ICA, settings)
├── requirements.txt           Python dependencies
├── templates/
│   ├── base.html              Shared layout (sidebar + nav)
│   ├── home.html              Dashboard with stats and feature cards
│   ├── check.html             Check Box Folder (scan + file table)
│   ├── extract.html           Run extraction pipeline
│   └── chat.html              AI Assistant chat UI
├── static/
│   └── style.css              Full UI stylesheet
├── Word Extracts/             .docx exports
├── CSV Extracts/              .xlsx exports
├── JSON File Extracts/        .json exports
└── Log History/               Per-file extraction logs
```

---

## ICA Credentials

The AI Assistant uses **IBM Consulting Advantage (ICA) 1.0**. To get your credentials:

1. Open the **ICA Cookie Parser** tool: `../ICA Cookie Parser/ica_cookie_parser.html`
2. In your browser, open ICA and send any message
3. Open DevTools → Network → click the `entries` POST → Headers tab → copy all headers
4. Paste into the parser and click **Parse & Generate Config**
5. Copy the generated `"ica": { ... }` block into `config.json`

> ICA cookies expire periodically. Refresh them using the parser when the AI stops responding.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scan` | Scan Box folder, update tracking DB |
| `POST` | `/api/extract` | Start extraction pipeline (async) |
| `GET` | `/api/extract/status` | Poll extraction running state and result |
| `GET` | `/api/status` | Get file counts and Pending file list |
| `POST` | `/api/chat` | Send message to ICA assistant |
| `GET` | `/api/logs?period=day` | Get log history summary |

---

## AI Assistant — Chat Commands

| Command | What it does |
|---------|-------------|
| `scan` | Scan Box folder for PDFs |
| `extract` | Run extraction pipeline on all Pending files |
| `look up [name or ref]` | Display report data in chat |
| `file status` | Show Pending / Completed counts |
| `logs this week` | View extraction log history |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | Web framework |
| `boxsdk` | Box API client |
| `PyMuPDF` | Open and decrypt PDFs |
| `python-docx` | Generate Word `.docx` exports |
| `openpyxl` | Generate Excel `.xlsx` exports |

---

## Notes

- Box Developer Tokens expire after **60 minutes**. Refresh `box.access_token` in `config.json` before scanning or extracting.
- The extraction logic is shared with the desktop apps via `../PDF Extractor/pdf_text_extractor.py` (or a local copy).
- All extraction logs are written to `Log History/YYYY/MMM_YYYY/Week_NN/YYYY-MM-DD/`.
