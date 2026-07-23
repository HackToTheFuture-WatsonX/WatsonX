# Threat Model

STRIDE-style enumeration of threats against PDF Extractor V3. Each entry names the threat, the asset it targets, existing mitigations, and residual risk.

The scope is a **single Windows user session running V3 locally**. Threats requiring a compromised OS account are out of scope (an attacker with SYSTEM or the user's own credentials can already exfiltrate everything the user could).

---

## Assets

| Asset | Value | Where |
|---|---|---|
| PDF password | High — decrypts every source PDF | `config` table |
| Box JWT | High — Box-side write access | `jwt_config` table |
| ICA cookie | Medium — 8–24 h validity, personal to the IBMid | `config.ica.full_cookie` |
| Extracted PII (subject names, refs, employment history) | High — GDPR-scoped in EU jurisdictions | `Local Folder\Extracted\`, `pdf_extractor_v3.db` (tracking + logs) |
| Source PDFs | High — same PII content | `Local Folder\`, then `Local Folder\Archive\` |
| Activity log | Medium — reveals who processed what, when | `extraction_logs` table |

---

## STRIDE

### Spoofing

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| S-1 | Another local user impersonates the operator by launching V3 from their session | Windows file ACLs on `%APPDATA%\PDF Extractor V3\` restrict access to the account that installed | Low — assumes standard Windows profile hygiene |
| S-2 | Attacker forges a request to the local API pretending to be the renderer | API bound to 127.0.0.1; no CSRF token but not needed — no browser can navigate to a loopback origin from a remote page | Low |
| S-3 | Malicious app on the same machine impersonates V3 to Box | Box JWT is per service account; possession = auth. Attacker with read access to the DB has already won | Accepted — see [Security-Model.md](Security-Model.md#data-at-rest-protection) |

### Tampering

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| T-1 | Modification of `pdf_extractor_v3.db` while V3 is running | SQLite WAL mode + busy timeout; conflicting writes fail cleanly | Low |
| T-2 | Modification of exported `.docx / .xlsx / .json` files after extraction | No integrity check; a compromised local user can edit exports freely | Accepted — extracts are workflow outputs, not evidentiary artefacts |
| T-3 | Modification of `bee_prompt.md` in the packaged binary | PyInstaller bundle is opaque; tampering requires unpacking and re-signing (which isn't checked) | Low — outcome is a differently-behaving Bee, no privilege escalation |
| T-4 | Man-in-the-middle on Box or ICA HTTPS | TLS with root-CA validation via OS trust store | Low — assumes OS root store isn't tampered |
| T-5 | Prompt injection in a chat message directs Bee to reveal secrets | Bee's replies are streamed through the hallucination guard; Bee has no tools that reveal secrets even if convinced to; the local skills are keyword-routed and don't invoke ICA at all for structural commands | Low — no privilege escalation vector exists in current Bee tooling |

### Repudiation

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| R-1 | User denies performing an operation | Activity log records every user-visible action with timestamp + level. Log is append-only in the app; the user could still hand-delete rows from the DB | Medium — see below |
| R-2 | The log itself is altered to hide an action | No cryptographic chain. A knowledgeable user can `DELETE FROM extraction_logs WHERE …` | Accepted — this is a single-user local app; a tamper-evident log would require an external store |

### Information Disclosure

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| I-1 | Secrets leaked into activity log | `activity.write` on settings save uses the **masked** config diff. `_redact_cookie` always fingerprints, never dumps the value | Low |
| I-2 | Secrets leaked into stdout/stderr → backend log | `pdf_password` is never logged. Cookie is only logged via `_redact_cookie` | Low |
| I-3 | Secrets returned to the frontend | `_mask_config` masks `pdf_password` and `ica.full_cookie` unconditionally on GET | Low |
| I-4 | Extracted PII is leaked via chat replies to unauthorised parties | Only the local user can hit the chat endpoint (loopback API) | Low |
| I-5 | Someone with disk access reads `pdf_extractor_v3.db` | Windows ACL on the parent dir; disk-level BitLocker if enabled by the enterprise | Medium — no in-app encryption at rest; see [Roadmap.md](Roadmap.md) |
| I-6 | ICA login window's persisted session lingers between sign-ins | `clearIcaLoginSession()` clears the partition storage on window close | Low |
| I-7 | Uploaded file with a traversal-crafted filename escapes `Local Folder/` | `Path(name).name` reduces to basename; extension whitelist enforces `.pdf` | Low |
| I-8 | Third-party MCP-style bridge exposes DB content to the network | No such bridge exists. Only Box and ICA are network endpoints | Low |

### Denial of Service

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| D-1 | Large PDFs exhaust memory | PyMuPDF streams; docs are closed after use | Low — very large PDFs still spike RAM temporarily |
| D-2 | Malicious Box folder with millions of items | `folder.get_items(limit=1000)` caps per call; long lists slow Sync but don't hang V3 | Low — sync is single-threaded and cancellable |
| D-3 | Local disk fills up during extraction | Extraction proceeds file-by-file; failure of one write does not corrupt others; error is reported per file | Low |
| D-4 | Repeated concurrent triggers from Chat commands | Each pipeline enforces single-instance via `_status["running"]` | Low — second trigger returns `already_running` |
| D-5 | Renderer memory leak from long-lived chat history | Zustand store is bounded by user behaviour; can be cleared by refreshing | Accepted |

### Elevation of Privilege

| # | Threat | Mitigation | Residual |
|---|---|---|---|
| E-1 | Renderer exploits nodeIntegration to run Node.js code | `nodeIntegration: false` + `contextIsolation: true`. Renderer sees only the three functions exposed via `contextBridge` | Low |
| E-2 | Malicious markdown in a chat reply triggers XSS | React auto-escapes; the chat pane renders Bee replies as text, not HTML | Low |
| E-3 | Path traversal in `os.startfile(path)` (View / chat "generate report" flow) | Paths come from the local DB and export directory only; user can't inject arbitrary paths | Low — assumes the DB itself isn't attacker-controlled |
| E-4 | PyInstaller frozen binary loads a malicious DLL via search-path hijack | PyInstaller resolves imports from `_MEIPASS`; system DLL search order is unchanged | Accepted — standard Windows DLL-hijack risk; V3 doesn't drop into `C:\Program Files` for portable |

---

## Threat Priorities

Ranking by residual risk × impact:

1. **I-5** — DB at rest not encrypted. Highest residual for compliance-oriented deployments. Mitigation on the [Roadmap.md](Roadmap.md).
2. **R-2** — activity log is tamperable by the same user who wrote it. Acceptable for a single-user tool; requires an external service to fix.
3. **T-5 / E-2** — prompt injection / XSS. Currently theoretical; no privilege-escalation vector exists.

---

## Out of Scope

- Physical access attacks (attacker with the laptop).
- Compromise of Box or ICA infrastructure.
- Supply-chain attacks on PyPI / npm dependencies (mitigated by pinning + code review at build time).
- Denial of the Box or ICA services from the vendor side.

---

## Related

- [Security-Model.md](Security-Model.md)
- [Data-Flow.md](Data-Flow.md)
- [Compliance.md](Compliance.md)
- [Audit-Logs.md](Audit-Logs.md)
