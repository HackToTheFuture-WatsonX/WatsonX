# WatsonX Challenge - Web App — Process Flows

## User Journey: First-Time Setup

```mermaid
flowchart TD
    A[Install Python 3.10+] --> B[pip install -r requirements.txt\nAlso install shared PDF deps]
    B --> C[Create Box App → JWT / Server Authentication\nat app.box.com/developers/console]
    C --> D[Download box_jwt_config.json\nPlace in WatsonX Challenge - Web/]
    D --> E[Fill in config.json:\nbox folder IDs, jwt_config_file]
    E --> F[Optional: add IBM Cloud API key\nfor watsonx.ai + Orchestrate]
    F --> G[Optional: add ICA cookies\nfor ICA 1.0 fallback]
    G --> H[python start_server.py]
    H --> I[Browser opens http://localhost:5000\nHome dashboard visible]
```

---

## User Journey: Daily Extraction Workflow

```mermaid
flowchart TD
    A[Open http://localhost:5000] --> B[Click Check Box Folder]
    B --> C[Click Scan Box Folder]
    C --> D{Scan returns files?}
    D -- No files --> E[Come back later]
    D -- Yes --> F[Review Pending file table]
    F --> G[Click Extract Files]
    G --> H[Click Start Extraction]
    H --> I[Page polls /api/extract/status\nShows live progress updates]
    I --> J[Extraction finishes]
    J --> K[Review result summary\n✅ N succeeded / ❌ M failed]
    K --> L[Optional: Insights — view chart]
    L --> M[Optional: AI Assistant\nlook up a report by name]
```

---

## Backend Process: Extraction Pipeline (Web App)

```mermaid
flowchart TD
    START([POST /api/extract]) --> LOCK{_extract_running?}
    LOCK -- Yes --> BUSY([Return: already running])
    LOCK -- No --> FLAG[Set _extract_running = True\nStart background thread]
    FLAG --> RESP([Return: started immediately])

    FLAG --> LOADCFG[Load config.json]
    LOADCFG --> JWTAUTH[JWT auth to Box\nauto-rotated — no expiry]
    JWTAUTH --> LIST[List PDFs in source folder_id]
    LIST --> LOOP{For each PDF}

    LOOP --> DL[Download bytes from Box into memory]
    DL --> DECRYPT[Decrypt with pdf_password]
    DECRYPT --> PARSE[Parse via shared engine\nbuild_structured_json()]
    PARSE --> EXPORTLOCAL[Export to local dated folders:\nWord / CSV / JSON Extracts/]

    EXPORTLOCAL --> UPLOAD{output_folder_id\nconfigured?}
    UPLOAD -- Yes --> BOXUP[Upload 3 files to Box\ndated path per ref]
    UPLOAD -- No --> SKIP_UP[Skip Box upload]

    BOXUP & SKIP_UP --> ARCHIVE{archive_folder_id\nconfigured?}
    ARCHIVE -- Yes --> MOVE[Move source PDF\nto archive_folder_id on Box]
    ARCHIVE -- No --> SKIP_ARCH[Skip archive]

    MOVE & SKIP_ARCH --> MARK[Mark Completed in tracking_db]
    MARK --> LOG[Write .log to Log History/]
    LOG --> LOOP

    LOOP -- "All done" --> DONE[Set _extract_running = False\nStore summary in _extract_result]
```

---

## Backend Process: AI Chat Routing

```mermaid
flowchart TD
    REQ["POST /api/chat\n{message, history}"]
    NORM[Normalize message to lowercase]
    CMD{Contains\naction keyword?}

    CMD -- "scan" --> SKILL_SCAN["skill_scan_box_folder()"]
    CMD -- "extract" --> SKILL_EXT["skill_run_extraction()"]
    CMD -- "look up" --> SKILL_LU["skill_lookup_report(query)"]
    CMD -- "file status" --> SKILL_ST["skill_get_file_status()"]
    CMD -- "logs" --> SKILL_LOG["skill_get_log_history(period)"]
    CMD -- "generate report" --> SKILL_GEN["skill_generate_reports(query)"]
    CMD -- "Free-form" --> WX

    WX{watsonx.ai\nconfigured?}
    WX -- Yes --> WXCALL["watsonx_chat(history, msg)"]
    WXCALL --> OK1{HTTP 200?}
    OK1 -- Yes --> REPLY
    OK1 -- No --> ORCH

    WX -- No/Error --> ORCH{Orchestrate\nconfigured?}
    ORCH -- Yes --> ORCHCALL["orchestrate_chat(history, msg)"]
    ORCHCALL --> OK2{HTTP 200?}
    OK2 -- Yes --> ACTION{"[ACTION:*]\ntag in reply?"}
    ACTION -- Yes --> EXEC["Execute tagged skill\nthen return combined reply"]
    ACTION -- No --> REPLY
    OK2 -- No --> ICA

    ORCH -- No/Error --> ICA{ICA 1.0\nconfigured?}
    ICA -- Yes --> ICACALL["ica_chat(history, msg)"]
    ICACALL --> OK3{HTTP 200?}
    OK3 -- Yes --> REPLY
    OK3 -- No --> WACHAT

    ICA -- No/Error --> WACHAT{Watson Assistant\nconfigured?}
    WACHAT -- Yes --> WACALL["watson_assistant_chat(msg)"]
    WACALL --> REPLY
    WACHAT -- No/Error --> FALLBACK["Return static help/error text"]
    FALLBACK --> REPLY

    SKILL_SCAN & SKILL_EXT & SKILL_LU & SKILL_ST & SKILL_LOG & SKILL_GEN --> REPLY
    EXEC --> REPLY
    REPLY["Return JSON\n{reply: string}"]
```

---

## User Journey: AI Report Lookup

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant Flask as app.py
    participant Box as IBM Box output folder
    participant Local as JSON File Extracts/

    User->>Browser: "look up Manalo"
    Browser->>Flask: POST /api/chat {message: "look up Manalo"}
    Flask->>Flask: Detect "look up" → skill_lookup_report("Manalo")
    Flask->>Box: Walk output_folder_id recursively for .json files
    Box-->>Flask: All extracted JSON reports
    Flask->>Flask: Filter: "manalo" in subject_name OR case_reference
    Flask->>Flask: Deduplicate by case_reference (keep latest extracted_at)
    alt Box unreachable
        Flask->>Local: Walk JSON File Extracts/ for .json files
        Local-->>Flask: Local JSON reports
    end
    Flask->>Flask: Format with §SECTION§ markers
    Flask-->>Browser: JSON {reply: formatted text}
    Browser->>Browser: JS renders §markers as styled HTML cards
    Browser-->>User: Visual structured report
```

---

## Process: Single-Instance Guard (start_server.py)

```mermaid
flowchart TD
    A[Double-click Start WatsonX Server.exe\nor python start_server.py]
    A --> B{Try to bind\nlocalhost:47321}
    B -- Port free --> C[Clear __pycache__]
    C --> D[Start Flask on port 5000]
    D --> E[Open browser after 2s delay]
    E --> F[Server runs until Ctrl+C]
    F --> G[Clear __pycache__ on shutdown]
    B -- Port taken\nanother instance running --> H[Open browser tab only\ndo not start second server]
    H --> I[Press Enter to close window]
```

---

## Process: Dated Output Folder + Box Mirror

The web app writes locally AND mirrors the same hierarchy on Box:

**Local:**
```
Word Extracts/2026/Jul_2026_Extracts/Week_28/2026-07-11/RN-123456/RN-123456.docx
```

**Box (`output_folder_id`):**
```
output_folder_id/2026/Jul_2026_Extracts/Week_28/2026-07-11/RN-123456/RN-123456.docx
```

Subfolders are created on Box on-demand using `_box_get_or_create_subfolder()`. If the subfolder already exists, it is reused.
