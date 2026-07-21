# Data Flow

DFD (Data Flow Diagram) levels 0–2 for PDF Extractor V3. Complements [Security-Model.md](Security-Model.md) and [Compliance.md](Compliance.md) — this doc shows *what* moves; those show *what's protected*.

---

## Level 0 — Context Diagram

```mermaid
graph LR
    User["👤 HR Operator"]
    V3["📦 PDF Extractor V3<br/>(desktop app)"]
    Box["☁️ IBM Box"]
    ICA["🤖 IBM Consulting Advantage"]

    User -->|"clicks & config"| V3
    V3 -->|"Word / Excel / JSON exports"| User

    Box -->|"encrypted PDFs"| V3
    V3 -->|"exported outputs<br/>+ archived source"| Box

    V3 -->|"prompt · cookie"| ICA
    ICA -->|"answer (SSE stream)"| V3
```

Three external actors: the user, IBM Box, and IBM Consulting Advantage.

---

## Level 1 — Major Data Stores

```mermaid
graph TB
    User

    subgraph Store["Local Data Store — %APPDATA%\\PDF Extractor V3\\"]
        DB[("pdf_extractor_v3.db<br/>config · tracking · JWT · logs")]
        LocalFolder["📁 Local Folder\\<br/>synced PDFs"]
        Extracted["📄 Local Folder\\Extracted\\<br/>Word · Excel · JSON"]
        Archive["📁 Local Folder\\Archive\\<br/>post-extraction source"]
    end

    subgraph V3["V3 Application"]
        Sync["🔄 Sync"]
        Scan["🔍 Scan"]
        Upload["⬆️ Upload"]
        Extract["⚙️ Extract"]
        View["👁 View"]
        Chat["💬 Chat"]
        Settings["⚙️ Settings"]
    end

    Box["☁️ IBM Box"]
    ICA["🤖 ICA"]

    User -->|"credentials"| Settings --> DB
    User -->|"trigger"| Sync
    User -->|"picked files"| Upload
    User -->|"trigger"| Extract
    User -->|"free-form message"| Chat
    User -->|"open"| View

    Sync <-->|"list + download"| Box
    Sync -->|"write file"| LocalFolder
    Sync -->|"archive-move"| Box
    Sync -->|"activity row"| DB

    Upload -->|"write file"| LocalFolder
    Upload -->|"tracking row + activity row"| DB

    Scan -->|"tracking upsert"| DB

    Extract -->|"read PDF"| LocalFolder
    Extract -->|"write exports"| Extracted
    Extract -->|"upload exports (optional)"| Box
    Extract -->|"move source"| Archive
    Extract -->|"tracking + activity"| DB

    View -->|"open file"| Extracted

    Chat -->|"read tracking / DB"| DB
    Chat -->|"read JSON"| Extracted
    Chat <-->|"prompt / answer"| ICA
    Chat -->|"activity"| DB
```

Stores:

| Store | Contents | Persistence |
|---|---|---|
| `pdf_extractor_v3.db` | Config, tracking, JWT, activity log (see [Database-Schema.md](Database-Schema.md)) | SQLite, WAL journal, backed by disk |
| `Local Folder\` | Synced source PDFs before extraction | NTFS files |
| `Local Folder\Extracted\` | Word/Excel/JSON exports in a dated hierarchy | NTFS files |
| `Local Folder\Archive\` | Post-extraction source PDFs | NTFS files |

---

## Level 2 — Extraction Pipeline

```mermaid
graph LR
    Src["📄 Encrypted PDF<br/>in Local Folder\\"]

    Decrypt["1️⃣ Decrypt<br/>PyMuPDF + password"]
    Text["2️⃣ Extract text<br/>per page"]
    Parse["3️⃣ Structured JSON<br/>report_summary · employment_checks · references · other_checks"]
    Ref["4️⃣ Derive ref_number<br/>case_reference OR filename stem"]

    subgraph Exports["5️⃣ Emit outputs — dated hierarchy"]
        Word[".docx via python-docx"]
        Excel[".xlsx via openpyxl"]
        JSON[".json via json.dump"]
    end

    BoxUp["6️⃣ Box upload<br/>(if output_folder_id set)"]
    Move["7️⃣ Move source<br/>to Archive/"]
    DB[("8️⃣ Update tracking<br/>+ write activity log")]

    Src --> Decrypt --> Text --> Parse --> Ref --> Exports
    Exports --> BoxUp
    Exports --> Move
    Src -.identity.-> Move
    Move --> DB
    BoxUp --> DB
```

Every step is idempotent given the same inputs: re-running Extract over a partial file re-produces the same outputs (subject to filename collision suffixing) and rewrites the same tracking row.

---

## Level 2 — Chat Data Flow

```mermaid
graph TB
    User["User message"]
    Router["route_chat_message"]

    subgraph Local["Local Skills — no network"]
        LookUp["skill_lookup_report<br/>reads JSON exports"]
        OpenReport["_skill_open_report<br/>os.startfile"]
        ListAll["_skill_list_all_reports"]
        TriggerSync["trigger_sync_for_chat"]
        TriggerScan["trigger_scan_for_chat"]
        TriggerExtract["trigger_extraction_for_chat"]
        FileStatus["file status → tracking DB"]
        LogHistory["logs → activity DB"]
    end

    ICAPath["_ica_send_and_stream<br/>Two-POST flow"]
    Guard["_is_hallucinated_reply<br/>refuse fabricated content"]

    User --> Router
    Router -->|"regex match"| Local
    Router -->|"else"| ICAPath
    ICAPath --> Guard
    Local --> Reply["📩 Reply → user"]
    Guard -->|"pass"| Reply
    Guard -->|"fail"| RefuseMsg["Canned refusal"]
    RefuseMsg --> Reply
```

Local skills never call the network. The hallucination guard is applied only to ICA replies (local skills return structured content from our own JSON extracts).

---

## Data Categories

| Category | Examples | Where it lives |
|---|---|---|
| **Auth material** | Box JWT, ICA cookie, PDF password | `pdf_extractor_v3.db` (masked at API boundary) |
| **Domain identifiers** | Box folder IDs, ICA team_id, chat_id | `pdf_extractor_v3.db` (unmasked) |
| **PII (subject data)** | Names, references, employment history from parsed reports | `pdf_extractor_v3.db` (tracking, activity), `Local Folder\Extracted\` |
| **Source documents** | Vendor PDFs | `Local Folder\` before extraction; `Local Folder\Archive\` after |
| **Operational telemetry** | Sync/scan/extract counts, timestamps | `extraction_logs` table + backend log |
| **Chat transcripts** | Local skill responses; ICA prompt/answer pairs | Frontend Zustand store (localStorage-persisted); NOT persisted server-side |

---

## Cross-boundary Data Movement

| Movement | Direction | Contents | Transport |
|---|---|---|---|
| Box source → V3 | in | Encrypted PDFs | HTTPS, `boxsdk` |
| V3 → Box archive | out | The same PDFs (Box-side move) | HTTPS, `boxsdk` |
| V3 → Box output | out | Exports mirroring the dated hierarchy | HTTPS, `boxsdk` |
| V3 → ICA | out | User message (or `bee_prompt.md`), auth cookie | HTTPS |
| ICA → V3 | in | Streamed answer chunks | HTTPS SSE |
| User → V3 | in | Clicks, form data, chat messages | Local UI |
| V3 → User | out | Renders, downloads, opened files | Local UI |

---

## Retention

See [Data-Retention.md](Data-Retention.md) for per-category policy.

---

## Related

- [Database-Schema.md](Database-Schema.md) — table shape
- [Security-Model.md](Security-Model.md) — trust boundaries around this flow
- [Compliance.md](Compliance.md) — regulatory framing
- [Audit-Logs.md](Audit-Logs.md) — how log rows are structured
