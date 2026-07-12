# Background Check Report Automation — Web App
### Powered by IBM watsonx Orchestrate

A Flask web application that mirrors every feature of the desktop app while integrating
**IBM watsonx Orchestrate** as the AI backbone for the chat assistant.

> **Desktop app is untouched.** This web version lives in its own folder and shares only
> the PDF parsing / export logic from `../PDF Extractor/pdf_text_extractor.py`.

---

## Project Structure

```
WatsonX Challenge - Web/
├── app.py                   ← Flask server + Orchestrate integration
├── config.json              ← All credentials (Box, Orchestrate, settings)
├── requirements.txt         ← Python dependencies
├── templates/
│   ├── base.html            ← Shared layout (sidebar + nav)
│   ├── home.html            ← Dashboard with stats + feature cards
│   ├── check.html           ← Check Box Folder (scan + file table)
│   ├── insights.html        ← Extraction statistics chart
│   ├── extract.html         ← Run extraction pipeline
│   └── chat.html            ← AI Assistant (Orchestrate-powered chat)
├── static/
│   └── style.css            ← Full UI stylesheet
├── Word Extracts/           ← .docx exports
├── CSV Extracts/            ← .xlsx exports
├── JSON File Extracts/      ← .json exports
└── Log History/             ← Per-file extraction logs
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```
> The web app also needs the desktop app's dependencies (PyMuPDF, python-docx, openpyxl, boxsdk).
> If not already installed, run from the PDF Extractor folder:
> ```bash
> pip install -r "../PDF Extractor/requirements.txt"
> ```

### 2. Configure credentials
Open `config.json` and fill in all required values (see sections below).

### 3. Run the server
```bash
python app.py
```
Then open **http://localhost:5000** in your browser.

---

## Configuration — `config.json`

### Box credentials (same as desktop app)
```json
"box": {
  "client_id":         "your_box_client_id",
  "client_secret":     "your_box_client_secret",
  "access_token":      "YOUR_BOX_DEVELOPER_TOKEN",
  "folder_id":         "123456789",
  "archive_folder_id": "987654321"
}
```
Generate a Developer Token at https://app.box.com/developers/console (valid 60 min).

---

### watsonx Orchestrate credentials

```json
"orchestrate": {
  "api_key":      "YOUR_IBM_CLOUD_API_KEY",
  "instance_url": "https://api.us-south.assistant.watson.cloud.ibm.com/instances/YOUR_INSTANCE_ID",
  "agent_id":     "YOUR_ORCHESTRATE_AGENT_ID"
}
```

#### Step-by-step: Getting Orchestrate credentials

**Step 1 — IBM Cloud API Key**
1. Go to https://cloud.ibm.com → **Manage → Access (IAM) → API Keys**
2. Click **Create an IBM Cloud API key**
3. Copy the key (shown only once) → paste into `config.json → orchestrate.api_key`

**Step 2 — Orchestrate Instance URL**
1. Go to https://cloud.ibm.com → search **"watsonx Orchestrate"** in the catalog
2. Open your provisioned instance
3. Copy the **instance URL** from the browser address bar or the **Credentials** tab
   - Format: `https://api.us-south.assistant.watson.cloud.ibm.com/instances/<id>`
4. Paste into `config.json → orchestrate.instance_url`

**Step 3 — Create an Orchestrate Agent**
1. Open your Orchestrate instance → **Agents** → **Create Agent**
2. Name it: `Background Check Assistant`
3. Set the system prompt (see below)
4. Copy the **Agent ID** from the URL or Agent Settings
5. Paste into `config.json → orchestrate.agent_id`

**Recommended Agent System Prompt:**
```
You are an AI assistant for the Background Check Report Automation application.
You help users understand background check reports and trigger application tasks.

You can answer questions about:
- Subject names, case references, overall status (Cleared / Not Cleared)
- Employment checks — employer, position, dates, rehire eligibility
- Professional reference checks — referee name, Q&A, result
- Database checks — Adverse Media, Global Sanctions, Bankruptcy, Financial/Credit,
  Directorship, Civil Litigation, Professional License, Social Media Screening

When asked to perform an action, use one of these exact tags in your reply:
  [ACTION:SCAN]         — scan the Box folder for new PDF files
  [ACTION:EXTRACT_CHAT] — run the full PDF extraction pipeline
  [ACTION:STATUS]       — show current Pending / Completed file counts
  [ACTION:LOGS_DAY]     — show today's extraction log history
  [ACTION:LOGS_WEEK]    — show this week's extraction log history
  [ACTION:LOGS_MONTH]   — show this month's extraction log history

Be concise, professional, and helpful.
```

---

## How watsonx Orchestrate is Used

```
User types a message
      │
      ▼
POST /api/chat   (app.py)
      │
      ├─► Local keyword shortcuts (scan, extract, status, logs)
      │         └─► Handled instantly without calling Orchestrate
      │
      └─► All other messages → orchestrate_chat()
                │
                ▼
        1. Exchange IBM Cloud API key for Bearer token (IAM)
        2. Create an Orchestrate session
        3. POST the message to the agent
        4. Agent reasons, optionally calls skills, returns reply
        5. Parse [ACTION:*] tags → execute local skills
        6. Return combined reply to browser
```

### Orchestrate Skills (exposed as REST endpoints callable by the agent)

| Skill function | What it does |
|---|---|
| `skill_scan_box_folder()` | Scans Box folder, updates tracking DB |
| `skill_run_extraction()` | Runs the full PDF extraction pipeline |
| `skill_lookup_report(query)` | Searches extracted JSON reports |
| `skill_get_log_history(period)` | Returns log history for day/week/month/year |
| `skill_get_file_status()` | Returns Pending / Completed counts |

---

## Graceful Degradation (No Orchestrate Yet)

The chat assistant **works without Orchestrate configured**. If credentials are missing,
it falls back to direct local skill calls triggered by natural-language keywords:

| You say | What happens |
|---|---|
| "scan box" | Triggers `skill_scan_box_folder()` directly |
| "run extraction" | Starts the pipeline in a background thread |
| "file status" | Returns Pending / Completed counts |
| "look up [name]" | Searches extracted JSON reports |
| "logs today/week/month" | Returns log history |

---

## Pages

| URL | Screen |
|---|---|
| `/` | Home — dashboard with stat cards and navigation |
| `/check` | Check Box Folder — scan Box, view Pending files |
| `/insights` | Insights — bar chart of extractions over time (Chart.js) |
| `/extract` | Extract Files — start pipeline, live progress, result cards |
| `/chat` | AI Assistant — full chat UI powered by watsonx Orchestrate |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/scan` | Scan Box folder, update tracking DB |
| `POST` | `/api/extract` | Start extraction pipeline (async) |
| `GET` | `/api/extract/status` | Poll extraction running state + result |
| `GET` | `/api/status` | Get file counts + Pending file list |
| `GET` | `/api/insights?period=Month` | Get chart data bucketed by period |
| `POST` | `/api/chat` | Send message to Orchestrate agent |
| `GET` | `/api/logs?period=day` | Get log history summary |

---

## Differences from the Desktop App

| Feature | Desktop App | Web App |
|---|---|---|
| UI framework | Tkinter (Python) | Flask + HTML/CSS |
| AI integration | watsonx.ai (ModelInference) | watsonx Orchestrate (Agent API) |
| Chart library | Custom Canvas drawing | Chart.js |
| Access | Local desktop only | Any browser, any device on the network |
| Multi-user | Single user | Multiple concurrent users |
| Extraction logic | Shared — `pdf_text_extractor.py` | Shared — same file |
