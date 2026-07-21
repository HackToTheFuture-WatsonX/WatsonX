# Product Overview

## Executive Summary

**PDF Extractor V3** is a Windows desktop application that automates the end-to-end handling of background check reports — from downloading encrypted PDFs out of IBM Box to producing searchable Word, Excel, and JSON exports and answering natural-language questions about them via IBM Consulting Advantage (ICA).

It exists to eliminate manual PDF handling in HR operations. Prior to V3, staff opened each encrypted PDF, retyped verified fields into spreadsheets, and hunted through nested cloud folders for the resulting outputs. V3 collapses that workflow to five clicks: **Sync → Scan → Extract → View → (optional) Chat**.

## Product Category

Enterprise workflow automation client — a single-user desktop utility that runs entirely on the operator's machine and reaches out to IBM Box and ICA over authenticated HTTPS. No server component to deploy, no browser dependency, no Python install required on the target host.

## Primary Users

| User | Volume | Pain V3 solves |
|---|---|---|
| HR operations staff | Daily driver — 10s of reports/day | Manual re-keying of PDF data |
| Compliance reviewers | Occasional — audit sampling | Locating and opening exports |
| Managers | Weekly — throughput checks | Aggregating completion stats |
| Power users | Ad-hoc lookups | "Where's the report for X?" |

See [User-Personas.md](User-Personas.md) for detail.

## Distinguishing Characteristics

- **Portable single-file distribution** — one `.exe` bundles Chromium, Node.js, Python, all PyPI packages, and the React build. Runs from a USB drive.
- **Single-database persistence** — every piece of state (config, tracking, JWT credentials, activity logs) lives in `pdf_extractor_v3.db` under `%APPDATA%\PDF Extractor V3\`. No loose JSON to hand-edit.
- **Live telemetry** — every long-running operation streams progress to the UI over Socket.IO. Users see per-file status transitions in real time.
- **Auditable transactions** — every user-visible action (sync, scan, upload, extract, settings save, connection test, JWT upload, ICA prime) writes a levelled row to the `extraction_logs` table with a machine-readable `[[level=info|warning|error]]` marker.
- **AI-native lookup** — the built-in **Bee** assistant answers questions grounded in the exported JSON reports; it can also *trigger* sync/scan/extract on demand.

## What V3 Replaces

| Predecessor | Fate under V3 |
|---|---|
| PDF Extractor V1 (Tkinter, Box OAuth2) | Retained for reference; not receiving updates |
| PDF Extractor V2 (Tkinter, local sync + Box upload) | Superseded — V3 is the sanctioned client |
| Hand-managed `config.json` / `tracking_db.json` | Replaced by SQLite tables |
| `Log History/*.log` flat files | Replaced by the `extraction_logs` table |
| Manual ICA cookie copy-paste | Replaced by an in-app browser login window |

## Business Value

- **Throughput**: A batch of 50 pending reports that took a business day to process manually completes in minutes.
- **Consistency**: Every export follows the same three-file layout (Word / Excel / JSON) in the same dated folder hierarchy.
- **Traceability**: Every action is logged. `Ref: <case-reference>` links extraction logs back to source documents.
- **Portability**: A single `.exe` deploys to any Windows workstation without IT prerequisites.

## Non-Goals

V3 intentionally does **not**:

- Serve as a multi-user server (it is a single-operator desktop client — see [Threat-Model.md](Threat-Model.md)).
- Modify source PDFs (extraction is strictly read → export; the source is moved to `Local Folder\Archive\` on success).
- Provide role-based access control (the OS-level filesystem and Windows account are the trust boundary).
- Store secrets in an encrypted vault (they live in the local SQLite DB under Windows file permissions — see [Security-Model.md](Security-Model.md)).

## Related Documents

- [Feature-Scope.md](Feature-Scope.md) — feature inventory
- [Use-Cases.md](Use-Cases.md) — workflow scenarios
- [Technical-Architecture.md](Technical-Architecture.md) — how it's built
- [Roadmap.md](Roadmap.md) — where it's going
