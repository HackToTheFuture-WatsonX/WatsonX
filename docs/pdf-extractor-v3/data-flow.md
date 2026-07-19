# PDF Extractor V3 — Data Flow

This document describes how data moves through PDF Extractor V3. All data stores, transformations, and external integrations are V3-specific and self-contained — V3 uses a single SQLite database as its source of truth.

---

## Level 0 — System Context

> **Analogy:** Think of V3 as a fully automated post room. Sealed letters (encrypted PDFs) arrive in your company inbox (IBM Box). V3 opens every letter, reads it, types up a clean copy in three formats, files it in a dated cabinet, sends the copies back to headquarters, and tells an AI assistant what was in each letter so you can ask questions later.

```mermaid
flowchart LR
    HR["👤 HR / Operations User"]
    BOX_IN["☁️ IBM Box\nSource Folder\n(incoming PDFs)"]
    V3["⚙️ PDF Extractor V3\nElectron Desktop App"]
    BOX_OUT["☁️ IBM Box\nOutput + Archive Folders"]
    EXPORTS["📁 Local Exports\n.docx · .xlsx · .json"]
    ICA["🤖 IBM Consulting\nAdvantage (ICA)"]

    HR -- "Sync · Scan · Extract\nChat · Settings" --> V3
    BOX_IN -- "Encrypted PDF reports" --> V3
    V3 -- "Structured exports" --> BOX_OUT
    V3 -- "Structured exports" --> EXPORTS
    V3 -- "Status · results" --> HR
    EXPORTS -- "JSON report data" --> ICA
    HR -- "Natural language queries" --> ICA
    ICA -- "Report answers / actions" --> HR
```

---

## Level 1 — Major Internal Processes & Data Stores

```mermaid
flowchart TD
    BOX_SRC["☁️ IBM Box\nSource Folder"]

    SYNC["1. Sync\nDownload PDFs from Box\nArchive originals on Box"]
    SCAN["2. Scan\nWalk Local Folder\nRegister PDFs as Pending"]

    DB[("🗄️ SQLite Database\npdf_extractor_v3.db\n─────────────────\nconfig · tracking_files\njwt_config · extraction_logs")]

    EXTRACT["3. Extract\nDecrypt · Parse · Export\nUpload to Box · Archive locally"]

    LOCAL_FOLDER["📁 Local Folder\n*.pdf (incoming)"]
    EXPORTS["📁 Extracted/\nWord · Excel · JSON"]
    ARCHIVE_LOCAL["📁 Archive/\nProcessed source PDFs"]

    VIEW["4. View\nBrowse extracted files\nOpen in OS app"]
    INSIGHTS["5. Insights\nStats + chart from DB\nLog history from DB"]
    CHAT["6. Chat\nRoute intent\nLook up JSON files\nCall ICA if needed"]
    SETTINGS["7. Settings\nRead/write config in DB\nStore JWT in DB\nTest Box + ICA"]

    BOX_SRC -->|"PDF bytes"| SYNC
    SYNC -->|"Save file"| LOCAL_FOLDER
    SYNC -->|"Trigger after download"| SCAN
    SCAN -->|"Register + purge rows"| DB
    DB -->|"Pending file list"| EXTRACT
    EXTRACT -->|"Read PDF"| LOCAL_FOLDER
    EXTRACT -->|"Write Word · Excel · JSON"| EXPORTS
    EXTRACT -->|"Move source PDF"| ARCHIVE_LOCAL
    EXTRACT -->|"Update status · write log"| DB
    EXPORTS -->|"Show files"| VIEW
    DB -->|"tracking_files rows"| INSIGHTS
    DB -->|"extraction_logs rows"| INSIGHTS
    EXPORTS -->|"JSON files for lookup"| CHAT
    DB -->|"tracking counts"| CHAT
    DB -->|"Read / write config"| SETTINGS
    DB -->|"Read / write JWT"| SETTINGS
```

---

## Level 2 — Extract Process Detail

The Extract step is the most complex — a multi-stage pipeline per PDF file.

```mermaid
flowchart TD
    PENDING["Pending PDFs\nfrom tracking_files table"]

    DECRYPT["open_and_decrypt_pdf()\nPyMuPDF + pdf_password\nUnlock + open document"]

    EXTRACT_PAGES["extract_text_by_page()\nDump plain text per page\nStrip footer noise"]

    PARSE["build_structured_json()\nRoute pages to specialist parsers"]

    subgraph "Page Routing"
        P0["Cover page (page 0)\nparse_summary_page()\nSubject · status · case ref\nSummary verdict table"]
        EMP["Employment Check pages\nparse_employment_check()\nEmployer · dates · result · respondent"]
        REF["Reference Check pages\nparse_reference_check()\nReferee · Q&A pairs · result"]
        DB_CHECKS["Database Check pages\nparse_other_checks()\nAdverse Media · Sanctions\nBankruptcy · Credit · etc."]
    end

    XREF["Cross-reference\nSummary verdicts → detail sections"]
    STRUCTURED["Structured JSON document\n{report_summary, employment_checks,\nprofessional_reference_checks,\nother_checks}"]

    WORD["export_to_word()\n→ .docx"]
    EXCEL["export_to_csv()\n→ .xlsx"]
    JSON["export_to_json()\n→ .json"]

    UPLOAD["upload_file_to_box()\nMirror folder hierarchy on Box\nCreate subfolders if needed"]
    ARCHIVE["Move source PDF\nto Archive/"]
    LOG["db.log_add()\nWrite extraction log\nto extraction_logs table"]
    UPDATE_DB["db.tracking_replace_all()\nstatus = Completed\nref_number · last_extracted\narchive_path"]

    PENDING --> DECRYPT
    DECRYPT --> EXTRACT_PAGES
    EXTRACT_PAGES --> PARSE
    PARSE --> P0
    PARSE --> EMP
    PARSE --> REF
    PARSE --> DB_CHECKS
    P0 & EMP & REF & DB_CHECKS --> XREF
    XREF --> STRUCTURED
    STRUCTURED --> WORD
    STRUCTURED --> EXCEL
    STRUCTURED --> JSON
    WORD & EXCEL & JSON --> UPLOAD
    WORD & EXCEL & JSON --> ARCHIVE
    WORD & EXCEL & JSON --> LOG
    LOG --> UPDATE_DB
```

---

## Level 2 — Chat Intent Routing

How a user message becomes a response.

```mermaid
flowchart TD
    MSG["Incoming message\n+ conversation history"]
    SANITIZE["_sanitize_history()\nReplace hallucinated assistant turns\nwith safe fallback text"]

    KW{Keyword\nmatch?}

    SYNC_H["trigger_sync_for_chat()\n→ sync_box_to_local()\nReturns download summary"]
    SCAN_H["trigger_scan_for_chat()\n→ run_scan()\nReturns count summary"]
    EXTRACT_H["trigger_extraction_for_chat()\n→ run_extraction()\nReturns LINKS payload"]
    STATUS_H["load_tracking() from DB\nReturns Pending / Completed counts"]
    LOGS_H["get_log_history(period)\ndb.logs_since() → DB query\nReturns formatted log text"]
    LOOKUP_H["skill_lookup_report()\nrglob JSON File Extracts/\nName/ref matching\nFormats report block"]
    GEN_H["_find_report_files()\nMatch → pick file type\nos.startfile() to open"]
    ICA_H["ica_chat()\nPOST to ICA API\nPoll for ANSWER entry\nHallucination check"]
    HELP["Return help menu\n(ICA not configured)"]

    MSG --> SANITIZE
    SANITIZE --> KW
    KW -- sync --> SYNC_H
    KW -- scan --> SCAN_H
    KW -- extract --> EXTRACT_H
    KW -- file status --> STATUS_H
    KW -- logs --> LOGS_H
    KW -- look up / find --> LOOKUP_H
    KW -- generate report --> GEN_H
    KW -- "no match + ICA configured" --> ICA_H
    KW -- "no match + ICA not configured" --> HELP
```

---

## Data Inputs and Outputs

### Inputs

| Source | Format | What It Contains |
|---|---|---|
| IBM Box source folder | Encrypted PDF | Background check report — cover page + section detail pages |
| `config` DB table | JSON (per section) | Box credentials, PDF password, ICA session, folder paths, settings |
| `jwt_config` DB table | JSON | Box JWT service-account key material |
| User interactions | Button click / chat message | Sync trigger, extract trigger, AI query |

### Data Stores

| Store | Type | Updated By | Read By |
|---|---|---|---|
| `config` table | SQLite | Settings page (`POST /api/settings`) | All modules via `config.read_config()` |
| `tracking_files` table | SQLite | Scanner, Extractor | Scanner, Extractor, Insights, Chat |
| `jwt_config` table | SQLite | Settings page (`POST /api/settings/jwt`) | `box_client.get_box_client()` |
| `extraction_logs` table | SQLite | Extractor (`db.log_add()`) | Insights (`db.logs_since()`), Chat |
| `Local Folder/Extracted/` | `.docx` `.xlsx` `.json` files | Extractor | View page, Chat (`skill_lookup_report`), users |
| `Local Folder/Archive/` | `.pdf` files | Extractor (move after success) | View page |
| IBM Box output folder | `.docx` `.xlsx` `.json` | Extractor (upload) | External consumers, auditors |

### Outputs

| Output | Format | Destination | Consumer |
|---|---|---|---|
| Structured report | `.json` | Local Extracted/ + Box | AI assistant, integrations |
| Formatted report | `.docx` | Local Extracted/ + Box | HR reviewers, auditors |
| Tabular report | `.xlsx` | Local Extracted/ + Box | Data analysis, reporting |
| Extraction log | `extraction_logs` row | SQLite DB | Insights logs view, Chat `logs` command |
| Status update | `tracking_files` row | SQLite DB | Next scan / extract / insights / chat cycle |

---

## Structured JSON Output Schema

The core transformation takes an unstructured PDF text dump and produces this document stored as a `.json` file on disk (and searchable by the Chat assistant):

```json
{
  "source_file": "RN-123456_789_10.pdf",
  "extracted_at": "2026-07-10T14:23:03",
  "total_pages": 12,
  "report_summary": {
    "subject_name": "Smith, John",
    "overall_status": "Cleared",
    "case_reference": "RN-123456_789_10",
    "case_received": "2026-06-15",
    "package": "Standard",
    "delivery_date": "2026-07-08",
    "employment_check_summary": [
      { "employer": "Acme Corp", "result": "Verified – Clear", "status": "Cleared" }
    ],
    "professional_reference_summary": [],
    "database_check_summary": [
      { "check": "Adverse Media Check", "result": "No Adverse", "status": "Cleared" }
    ]
  },
  "employment_checks": [
    {
      "check_number": 1,
      "employer_name": "Acme Corp",
      "position_title": "Software Engineer",
      "dates_of_employment": "Jan 2020 – Dec 2023",
      "verification_status": "Cleared",
      "result": "Verified – Clear",
      "notes": ""
    }
  ],
  "professional_reference_checks": [],
  "other_checks": [
    { "check_name": "Adverse Media Check", "status": "Cleared", "source": "...", "result": "No Adverse" },
    { "check_name": "Global Sanctions",    "status": "Cleared" }
  ]
}
```

---

## Status Values

The extraction engine uses exactly three status values. Ambiguity always defaults to `--`.

| Value | Meaning | Example Match |
|---|---|---|
| `Cleared` | Positive verification | "Verified – Clear", "No Adverse", "No Civil Case" |
| `Not Cleared` | Negative result | "Not Verified", "Red Flag", "Unverified" |
| `--` | Unknown / inconclusive | No keyword found — safe default, never a guess |
