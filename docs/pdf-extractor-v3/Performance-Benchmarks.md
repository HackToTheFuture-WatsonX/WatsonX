# Performance Benchmarks

Measured or reasoned estimates for V3's throughput, memory, disk, and network characteristics. Numbers are indicative — validate on your own hardware before making commitments.

Test machine reference: Windows 11 Pro, Intel i7 12th gen, 32 GB RAM, NVMe SSD, 1 Gbps ethernet.

---

## Startup

| Metric | Cold (first launch) | Warm (subsequent) |
|---|---|---|
| Splash to main window | 6–8 s | 4–6 s |
| Backend `Started server process` | 4–6 s after spawn | 3–5 s |
| Renderer `did-finish-load` | 200–400 ms after `loadFile` | same |

Splash appears in <100 ms — the perceived launch feels immediate because the dark splash is a `data:` URI, not a file load.

Startup is dominated by:

1. PyInstaller unpacking `_MEIPASS` (~2 s).
2. Python interpreter warm-up + module imports (~1–2 s).
3. FastAPI + Socket.IO + uvicorn initialization (~0.5 s).
4. First `/api/health` poll succeeding (0.5–1 s).

Portable exe adds ~2–3 s on first launch because the whole bundle unpacks to `%TEMP%`.

---

## Sync (Box → Local)

Dominated by Box API latency and PDF size. Approximate throughput:

| Config | Files / minute | Notes |
|---|---|---|
| 10 PDFs, ~500 KB each, LAN | 30–50 | Bounded by `folder.get_items(limit=1000)` + per-item HTTP |
| 10 PDFs, ~2 MB each, remote | 15–25 | Same overhead, more bytes |
| 100 files, mixed sizes | ~50/min sustained | Box API rate-limits kick in above ~1000 rpm — not observed in normal use |

Each file entails:
- 1 × `folder.get_items` (once per subfolder, batched).
- 1 × `file.content()` (download).
- 1 × `file.move(archive)` (post-success).

Sync is single-threaded per run — parallelisation is not implemented.

---

## Scan

Local filesystem walk. Roughly:

| Config | Wall clock |
|---|---|
| 100 files in `Local Folder/` | <100 ms |
| 1000 files | ~500 ms |
| 10000 files | ~5 s |

Scan reads only file metadata (name, existence) and touches the tracking DB once at the end via `tracking_replace_all`. The bottleneck is the recursive `rglob('*.pdf')`.

Consider a full scan cheap.

---

## Extraction

The hot path. Wall-clock per file depends on PDF size and complexity:

| Page count / complexity | Wall clock per file |
|---|---|
| 5–10 page standard report | 2–4 s |
| 20–30 page report with tables | 4–8 s |
| Very large report with dozens of embedded images | 10–20 s |

Breakdown per file:
- Decrypt + open (PyMuPDF): ~50 ms.
- Text extraction (page-by-page): 100–500 ms.
- Structured parsing: 100–300 ms.
- Word export (python-docx): 300–800 ms.
- Excel export (openpyxl): 200–500 ms.
- JSON export: <10 ms.
- Box upload (if configured): 500 ms – 2 s per file, times 3 files.
- Local archive move: <50 ms.

Extraction is single-threaded per run. Parallelising could halve wall-clock for large batches but has not been implemented — would require a rework of `extractor.run_extraction` and careful synchronisation against the tracking DB and Socket.IO event stream.

---

## Chat (ICA)

The two-POST flow adds two HTTPS round trips per user turn:

| Metric | Value |
|---|---|
| POST PROMPT round-trip | 300–800 ms |
| POST ANSWER (SSE read to completion) | 2–8 s depending on prompt length + ICA load |
| End-to-end user-visible latency | 3–9 s per turn |

Priming with `bee_prompt.md` (~4 KB) takes ~4–7 s on the first call after login; subsequent chat turns are unaffected.

Local skills (`look up`, `sync`, `scan`, `extract`, `file status`, `logs`) reply in <200 ms — no network involved.

---

## Memory Footprint

Steady-state usage:

| Process | RAM |
|---|---|
| Electron main + renderer (Chromium) | ~200–300 MB |
| Backend (Python + PyMuPDF cached) | ~80–120 MB idle, up to ~250 MB during extraction |

Peak during a 50-file extraction batch: ~500 MB total. No memory leaks observed over hour-long sessions; PyMuPDF closes docs explicitly and Python's cyclic GC catches the rest.

---

## Disk Footprint

Per installed instance:

| Component | Size |
|---|---|
| NSIS-installed application | ~250 MB |
| Portable exe on disk | ~180 MB (compressed) |
| Portable at runtime (`%TEMP%\<random>\`) | ~350 MB (unpacked) |
| User data (`%APPDATA%\PDF Extractor V3\`, no extracts) | ~50 KB (empty DB) |
| User data with 1000 extracted reports | ~500 MB – 2 GB (dominated by Word/PDF/xlsx exports; JSON is <10 % of that) |

`pdf_extractor_v3.db` grows with `extraction_logs` — ~1 KB per activity row. 100 000 rows ≈ 100 MB. Trim policy: see [Data-Retention.md](Data-Retention.md).

---

## Network Usage

Only during Sync, Extract (Box upload), Chat (ICA), and connection tests. All to two endpoints:

- `api.box.com` (Box Content API)
- `servicesessentials.ibm.com` (ICA)

No other outbound traffic. No telemetry.

---

## Concurrency Limits

- **One sync at a time** — `_status["running"]` flag on each pipeline module.
- **One scan at a time** — same.
- **One extract at a time** — same.
- **Sync + Scan + Extract simultaneously** — technically permitted but not recommended; disk contention on the source folder and DB write conflicts (mitigated by WAL) can slow all three.
- **Multiple chat requests** — each `POST /api/chat/send` is independent; concurrent chats don't share state.

---

## Bottlenecks Ranked

1. **Box API round-trip latency** — dominates Sync and Extract-Box-upload wall clock.
2. **PDF layout complexity** — outliers can dominate Extract wall clock.
3. **ICA response time** — dominates Chat perceived latency.
4. **Python interpreter warm-up on cold start** — one-time cost.

---

## What Would Improve Numbers

- **Parallel extraction** — thread pool over the pending set. Estimated 2×–4× throughput on 4-core machines.
- **HTTP connection reuse to Box** — currently each request uses a fresh SSL handshake. `boxsdk` supports session reuse; not yet configured.
- **Signed exes** — removes SmartScreen delay (~2 s user click cost, not a technical delay but a UX one).
- **Incremental sync via Box event stream** — replaces polling with push. Higher engineering cost.

Tracked in [Roadmap.md](Roadmap.md).

---

## Related

- [Monitoring.md](Monitoring.md) — where to observe these numbers
- [System-Design.md](System-Design.md) — why the pipeline is single-threaded
- [Roadmap.md](Roadmap.md) — performance-oriented future work
