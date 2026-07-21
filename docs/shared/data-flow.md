# Shared Data Flow

This document describes how data moves through the shared extraction engine used by all three applications. The flow is identical regardless of which app triggers it.

---

## Level 0 — System Context

> **Analogy:** The whole system is a black box labeled "Report Processor." Reports go in from Box; structured data comes out — to Box, to local files, and to the AI.

```mermaid
flowchart LR
    HR["👤 HR User"]
    BOX_IN["☁️ IBM Box\n(Source Folder)"]
    SYSTEM["⚙️ Background Check\nReport Automation"]
    BOX_OUT["☁️ IBM Box\n(Output + Archive)"]
    AI["🤖 AI Assistant"]
    EXPORTS["📁 Local Exports\n(.docx / .xlsx / .json)"]

    HR -- "Scan / Extract / Chat commands" --> SYSTEM
    BOX_IN -- "Encrypted PDF files" --> SYSTEM
    SYSTEM -- "Structured exports" --> BOX_OUT
    SYSTEM -- "Structured exports" --> EXPORTS
    SYSTEM -- "Status / reports" --> HR
    EXPORTS -- "JSON report data" --> AI
    HR -- "Natural language queries" --> AI
    AI -- "Report answers / actions" --> HR
```

---

## Level 1 — Major Internal Processes

```mermaid
flowchart TD
    BOX_SRC["☁️ Box Source Folder\n(PDFs)"]
    SCAN["1. Scan\nDiscover PDF files\nand register as Pending"]
    TRACKDB[("📄 tracking_db.json\nPer-file state\nPending / Completed")]
    DOWNLOAD["2. Download\nStream PDF bytes\ninto memory"]
    DECRYPT["3. Decrypt\nPyMuPDF + pdf_password\nAuthenticate + unlock"]
    PARSE["4. Parse\nExtract text per page\nRoute to section parsers"]
    EXPORT["5. Export\nBuild .docx / .xlsx / .json\nWrite to dated folders"]
    UPLOAD["6. Upload\nSend exports to Box\noutput_folder_id"]
    ARCHIVE["7. Archive\nMove source PDF to\narchive_folder_id"]
    LOG["8. Log\nWrite per-file .log\nto Log History/"]
    JSON_STORE[("📁 JSON File Extracts\n(Structured reports)")]
    AI_QUERY["9. AI Lookup\nSearch JSON by name/ref\nReturn formatted report"]

    BOX_SRC --> SCAN
    SCAN --> TRACKDB
    TRACKDB -- "Pending files" --> DOWNLOAD
    DOWNLOAD --> DECRYPT
    DECRYPT --> PARSE
    PARSE --> EXPORT
    EXPORT --> JSON_STORE
    EXPORT --> UPLOAD
    UPLOAD --> ARCHIVE
    ARCHIVE --> TRACKDB
    EXPORT --> LOG
    JSON_STORE --> AI_QUERY
```

---

## Level 2 — Parse Process Detail

The Parse step is the most complex. Each page is routed to a specialist parser based on its section heading.

```mermaid
flowchart TD
    PAGES["Raw text pages\n(list of strings)"]
    FOOTER["strip_footer()\nRemove address / phone / email lines"]
    P0["Page 0 + Page 1\n(Cover + Social Media)"]
    P_REST["Pages 2+"]

    SUMMARY["parse_summary_page()\nExtract: subject_name,\noverall_status, case_reference,\nemp/ref/db summary rows"]

    ROUTE{Route by\nsection heading}
    EMP_PAGE["EMPLOYMENT CHECK (N)\nparse_employment_check()\nExtract employer, dates,\nresult, respondent"]
    REF_PAGE["PROFESSIONAL REFERENCE\nCHECK (N)\nparse_reference_check()\nExtract referee, Q&A pairs"]
    DB_PAGE["DATABASE CHECK sections\nparse_other_checks()\nExtract source, result\nper check type"]

    XREF["Cross-reference\nSummary verdicts\ninto detail sections"]
    JSON_OUT["build_structured_json()\nAssemble final document"]

    PAGES --> FOOTER
    FOOTER --> P0
    FOOTER --> P_REST
    P0 --> SUMMARY
    P_REST --> ROUTE
    ROUTE -- "EMPLOYMENT CHECK heading" --> EMP_PAGE
    ROUTE -- "PROFESSIONAL REFERENCE heading" --> REF_PAGE
    ROUTE -- "DB check headings" --> DB_PAGE
    SUMMARY & EMP_PAGE & REF_PAGE & DB_PAGE --> XREF
    XREF --> JSON_OUT
```

---

## Data Inputs and Outputs

### Inputs

| Source | Format | What It Contains |
|---|---|---|
| IBM Box source folder | Encrypted PDF | Background check report — cover page + section detail pages |
| `config.json` | JSON | Box credentials, PDF password, AI credentials, settings |
| User interaction | Button click / chat message | Scan trigger, extract trigger, AI query |

### Data Stores

| Store | Format | Updated By | Read By |
|---|---|---|---|
| `tracking_db.json` | JSON | Scan, Extraction pipeline | All app screens, Insights chart |
| `JSON File Extracts/` | JSON (one per report) | Extraction pipeline | AI assistant lookup skill |
| `Word Extracts/` | `.docx` | Extraction pipeline | Users (manual open / download) |
| `CSV Extracts/` | `.xlsx` | Extraction pipeline | Users (manual open / download) |
| `Log History/` | `.log` | Extraction pipeline | Log history view, AI `logs` command |
| IBM Box output folder | `.docx`, `.xlsx`, `.json` | Extraction pipeline (upload) | External consumers / auditors |

### Outputs

| Output | Format | Destination | Consumer |
|---|---|---|---|
| Structured report | `.json` | Local + Box | AI assistant, integration systems |
| Formatted report | `.docx` | Local + Box | HR reviewers, auditors |
| Tabular report | `.xlsx` | Local + Box | Data analysis, reporting |
| Extraction log | `.log` | Local `Log History/` | Audit trail, debugging |
| Status update | `tracking_db.json` | Local | Next scan / extract / insights cycle |

---

## Structured JSON Output Schema

The core transformation takes an unstructured PDF text dump and produces this document:

```json
{
  "source_file": "RN-123456_789_10.pdf",
  "extracted_at": "2026-07-10T14:23:03",
  "total_pages": 12,
  "report_summary": {
    "subject_name": "Manalo, Jeffrey",
    "overall_status": "Cleared",
    "case_reference": "RN-123456_789_10",
    "case_received": "2026-06-15",
    "package": "Standard",
    "delivery_date": "2026-07-08",
    "employment_check_summary": [
      { "employer": "Acme Corp", "result": "Verified – Clear", "status": "Cleared" }
    ],
    "professional_reference_summary": [...],
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
      "verification_status": "Cleared"
    }
  ],
  "professional_reference_checks": [...],
  "other_checks": [...]
}
```

---

## Status Values

The engine uses exactly three status values. Ambiguity always defaults to `--` — the system never guesses.

| Value | Meaning | Matched By |
|---|---|---|
| `Cleared` | Positive verification result | "Verified – Clear", "Cleared", "No Adverse", "No Civil Case", etc. |
| `Not Cleared` | Negative verification result | "Not Verified", "Red Flag", "Unverified", "Verified –" (followed by anything except "clear") |
| `--` | Unknown / inconclusive | No matching keyword found — safe default |
