# PDF Extractor V2

Background Check Report Automation — Version 2

## What's New in V2

| Feature | V1 | V2 |
|---------|----|----|
| PDF Source | Downloaded on-demand from Box during Extraction | **Synced to Local Folder first**, then extracted locally |
| "Check Box" screen | Scanned Box folder directly via API | **Replaced with "Scan Folder"** — scans Local Folder |
| Extracted output location | Word Extracts/ / CSV Extracts/ / JSON File Extracts/ in the app root | **Local Folder/Extracted/Word Extracts/** etc. |
| Post-extraction upload | None (source archived on Box) | **Uploads Word/Excel/JSON to Box output_folder_id** |
| AI Assistant data source | JSON File Extracts/ in app root | **Local Folder/Extracted/JSON File Extracts/** |
| Sync | None | **New 🔄 Sync Folder screen** — manual button + optional auto-schedule |

---

## Quick Start

### 1. Configure config.json

Open config.json and fill in your credentials:

`json
{
  "box": {
    "client_id":        "your_client_id",
    "client_secret":    "your_client_secret",
    "access_token":     "your_developer_token",
    "folder_id":        "398448580241",
    "output_folder_id": "YOUR_OUTPUT_BOX_FOLDER_ID"
  },
  "watsonx": {
    "api_key":    "your_watsonx_api_key",
    "project_id": "your_watsonx_project_id"
  }
}
`

Key fields:
- ox.folder_id — the **source** Box folder to sync PDFs FROM (398448580241)
- ox.output_folder_id — Box folder to **upload extracted files TO**
- sync.auto_sync_enabled — set 	rue to auto-sync on startup + at schedule
- sync.auto_sync_interval_minutes — how often to auto-sync (default 30)

### 2. Launch

Double-click Launch.vbs or run:
`
python pdf_extractor_ui_v2.py
`

---

## Workflow

`
Box (folder_id)
      │
      ▼ [🔄 Sync Folder]  ── manual button or auto-schedule
Local Folder/
  ├── report1.pdf
  ├── report2.pdf
  └── Extracted/           ← all outputs go here
        ├── Word Extracts/
        │     └── 2026/Jul_2026_Extracts/Week_28/2026-07-10/RN-123456/
        ├── CSV Extracts/
        └── JSON File Extracts/
              │
              └── [AI Assistant reads from here]
                        │
                        ▼ [⚙️ Extract Files → upload]
              Box (output_folder_id)
`

### Step-by-step:

1. **🔄 Sync Folder** — Click "Sync Now" to download all PDFs from Box folder 398448580241 to Local Folder/.
   - Enable auto-sync in config.json → sync.auto_sync_enabled: true
2. **📂 Scan Folder** — Click "Scan Local Folder" to detect PDFs and register them as Pending.
3. **⚙️ Extract Files** — Click "Start Extraction" to:
   - Read each Pending PDF from Local Folder/
   - Decrypt (password from pdf_password)
   - Parse and export Word / Excel / JSON → Local Folder/Extracted/
   - Upload all 3 output files to Box output_folder_id
   - Mark file Completed
4. **📊 Insights** — View extraction statistics over time.
5. **💬 AI Assistant** — Chat with the AI, grounded on the JSON files in Local Folder/Extracted/JSON File Extracts/.

---

## Folder Structure

`
PDF Extractor V2/
├── pdf_extractor_ui_v2.py    ← Main UI (run this)
├── pdf_text_extractor.py     ← Core extraction engine
├── config.json               ← Credentials & settings
├── tracking_db.json          ← Auto-created — per-file Pending/Completed state
├── Launch.vbs                ← Double-click to launch without console
├── requirements.txt          ← Python dependencies
│
├── Local Folder/             ← PDFs synced from Box
│   └── Extracted/            ← All extraction outputs
│       ├── Word Extracts/
│       ├── CSV Extracts/
│       └── JSON File Extracts/
│
└── Log History/              ← Per-file extraction logs
`

---

## Dependencies

Install once:
`
pip install -r requirements.txt
`

Required packages: oxsdk, PyMuPDF, python-docx, openpyxl

---

## Auto-Sync Configuration

In config.json:
`json
"sync": {
  "auto_sync_enabled": true,
  "auto_sync_interval_minutes": 30
}
`

- First sync fires 10 seconds after app launch
- Re-schedules itself every interval_minutes
- Status shown on the 🔄 Sync Folder screen

---

## Notes

- Box Developer Tokens expire after **60 minutes**. Refresh ox.access_token in config.json before syncing/uploading.
- The Extracted/ folder is automatically excluded from Scan so extracted PDFs are never re-queued.
- All extraction logs are written to Log History/YYYY/MMM_YYYY/Week_NN/YYYY-MM-DD/.
