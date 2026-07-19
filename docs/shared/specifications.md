# Shared Specifications

These requirements, constraints, and definitions apply to all three applications. App-specific requirements are documented in each app's own `improvements.md`.

---

## Functional Requirements (Shared)

### FR-01: Box Folder Scanning
- The system shall connect to IBM Box using configured credentials
- The system shall list all PDF files in the configured source folder, recursively when `settings.search_subfolders = true`
- Each discovered PDF shall be registered in `tracking_db.json` with status `Pending`
- A file still in the source folder shall always be set to `Pending`, regardless of prior extraction history

### FR-02: PDF Extraction Pipeline
- The system shall download each Pending PDF from Box into memory (no local temp file)
- The system shall decrypt password-protected PDFs using the `pdf_password` from `config.json`
- The system shall extract all text content page by page
- The system shall parse the following sections from each report:
  - Cover page summary (subject name, overall status, case reference, dates)
  - Employment Check detail pages (employer, dates, result, respondent)
  - Professional Reference Check detail pages (referee, Q&A pairs, result)
  - Database/Other Check pages (Adverse Media, Global Sanctions, Bankruptcy, Financial/Credit, Directorship, Civil Litigation, Professional License, Social Media Screening)
- The system shall cross-reference summary verdicts from the cover page into detail sections
- The system shall export one `.docx`, one `.xlsx`, and one `.json` file per processed PDF
- All exports shall be written to dated folder hierarchies (`YYYY/MMM_YYYY_Extracts/Week_NN/YYYY-MM-DD/ref/`)
- Each file shall be marked `Completed` in `tracking_db.json` after successful extraction
- A per-file extraction log shall be written to `Log History/` for every processed file

### FR-03: Tracking State
- The system shall persist file state (Pending / Completed) in `tracking_db.json`
- The tracking database shall store: Box file ID, filename, status, last_extracted timestamp, ref_number, archived flag
- The tracking database shall survive app restarts without data loss

### FR-04: Insights / Statistics
- The system shall display a count of Total, Completed, and Pending files
- The system shall display a bar chart of Completed vs Pending extractions, filterable by Day / Week / Month / Year

### FR-05: AI Assistant Chat
- The system shall provide a chat interface that responds to natural language queries
- The system shall support at minimum: `scan`, `extract`, `look up [name/ref]`, `file status`, `logs this week`

---

## Non-Functional Requirements (Shared)

### NFR-01: Responsiveness
- All network operations (Box API calls, AI chat) shall run on background threads
- The UI shall remain responsive during any extraction or scan operation

### NFR-02: Security
- PDF passwords and API credentials shall be stored in `config.json`, not hardcoded
- Report data shall be excluded from git

### NFR-03: Reliability
- A failed extraction for one file shall not stop processing of subsequent files
- Failed files shall remain `Pending` and be logged with the error message

### NFR-04: Auditability
- Every extraction run shall produce a timestamped `.log` file in `Log History/`
- Log files shall record: file name, reference number, completion time, archive status, upload IDs, and any errors

### NFR-05: Portability
- All file paths shall be resolved relative to the script's own directory (no hardcoded absolute paths)

### NFR-06: Compatibility
- All three apps shall produce structurally identical JSON output
- The shared engine module shall remain the single source of truth for parsing logic

---

## Constraints

| Constraint | Detail |
|---|---|
| **Python 3.10+** | Required for `list[dict]` type hints used throughout the codebase |
| **In-memory PDF processing** | Very large PDFs (>100 MB) may cause memory pressure; optimised for typical report sizes (<10 MB) |
| **Windows filenames** | Reference numbers are sanitised with `re.sub(r'[<>:"/\\|?*]', "_", ...)` for Windows compatibility |
| **Report format** | Parser is tuned to Corpnet Global Corp two-column PDF layout and ALL-CAPS section headings; different formats require parser changes |
| **Folder layout** | The web app and PDF Extractor must be siblings in the same parent directory for the shared engine import to work |

---

## Assumptions

1. All PDFs in the Box source folder are Corpnet Global Corp background check reports using the known layout
2. The `pdf_password` in `config.json` correctly decrypts all current reports
3. The Box source folder does not contain non-report PDFs that would be incorrectly parsed
4. Report status verdicts appear only on the cover page / page 2 summary — never only on detail pages
5. Section headings in the PDF are identifiable as ALL-CAPS text by regex
6. The `Case Reference No` field on the cover page is a reliable unique identifier per report

---

## Glossary

| Term | Plain-Language Definition |
|---|---|
| **Background Check Report** | A formal document from Corpnet Global Corp verifying a person's employment history, references, and database records |
| **Box / IBM Box** | A cloud file storage service (like Google Drive) where PDF reports are stored and managed |
| **Case Reference Number** | A unique code assigned to each background check case (e.g. `RN-123456_789_10`) |
| **Cleared** | The check result shows no issues — the candidate passed that particular verification |
| **Not Cleared** | The check result shows a problem — something did not verify correctly |
| **Pending** | A PDF file that has been found but not yet extracted |
| **Completed** | A PDF file that has been successfully extracted, exported, and archived |
| **Extraction** | The process of opening a PDF, reading its contents, and converting them into structured Word/Excel/JSON files |
| **Tracking DB** | A small file (`tracking_db.json`) that remembers the status (Pending/Completed) of each PDF file |
| **JWT** | A type of secure login method used by the web app to access Box permanently, without needing to refresh credentials |
| **Developer Token** | A short-lived password (60-minute expiry) used by the desktop apps to access Box |
| **ICA / IBM Consulting Advantage** | IBM's internal AI chat platform used as an AI assistant backend |
| **watsonx.ai** | IBM's AI model platform — the primary AI backend for the web app |
| **watsonx Orchestrate** | IBM's AI agent platform that can call "skills" (actions) on behalf of a user |
| **Skill** | A specific action the AI can take (e.g. scan for files, look up a report) |
| **Archive folder** | A Box folder where processed PDFs are moved after extraction, so they are not re-processed |
| **Output folder** | A Box folder where extracted Word/Excel/JSON files are uploaded after extraction |
| **Section heading** | ALL-CAPS text in a PDF that marks the start of a new check section (e.g. `EMPLOYMENT CHECK`) |
| **Footer stripping** | Removing repeated page headers/footers (address, phone, email) before parsing |
| **DFD** | Data Flow Diagram — a diagram showing how data moves through a system |
