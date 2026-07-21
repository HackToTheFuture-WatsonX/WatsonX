# Bug Report Process

How to report a bug so it can actually be fixed. Bad reports die in triage; complete ones ship a fix in the next release.

---

## Before You File

1. **Check [Troubleshooting.md](Troubleshooting.md)** — most reproducible symptoms have a documented fix.
2. **Check [FAQ.md](FAQ.md)** — the answer might already be "that's by design".
3. **Try once more with a fresh Diagnostics reading** — the Scan-page panel often reveals a simple cause.

If the answer still isn't there, file it.

---

## Where to File

- **GitHub issue** on the project repo, using the `bug` label.
- **Slack** DM the maintainer for anything Sev 1 (data loss risk or complete blockage). See [Incident-Response.md](Incident-Response.md).

---

## Required Fields

**All bug reports must include:**

1. **Version** — from Settings → footer, or the exe filename, or `GET /api/health`.
2. **Windows version** — Settings → System (build number matters).
3. **Steps to reproduce** — numbered, minimal, deterministic.
4. **Expected behaviour** — what should have happened.
5. **Actual behaviour** — what did happen.
6. **Frequency** — every time / intermittent / once-only.

**Bonus fields that turn a slow triage into a same-day fix:**

7. **Backend log** — attach `%TEMP%\pdf-extractor-v3-backend.log` (contains the last-launch narrative + every request line + Python tracebacks).
8. **Startup log** — attach `%TEMP%\pdf-extractor-v3-startup.log` (contains any uncaught Electron exception).
9. **Diagnostics panel screenshot** — for any Upload / Scan issue, expand the Diagnostics `<details>` on the Scan page and screenshot it. Contains the exact fetch outcome.
10. **Activity log excerpt** — copy the row from the Logs page (right-click → Copy). If a batch failed, include multiple rows.
11. **ICA log excerpt** — for chat / ICA issues, attach the relevant section of `%APPDATA%\PDF Extractor V3\ica.log`.

Do NOT include:

- Screenshots of the actual PDF content (PII).
- Copies of `pdf_extractor_v3.db` unless sanitised first (contains masked-in-app but readable-at-rest secrets).
- Extracted `.docx / .xlsx / .json` files (PII).

---

## Redaction Guide

When attaching logs, redact:

- Full cookies (already redacted by V3 — cookies appear as `<N chars, M cookies: name1, name2, …>` — leave that intact).
- Subject names in activity logs (replace with `[REDACTED-NAME]`).
- Case reference numbers if they map to real cases (replace with `BG-REDACTED-N`).

For the DB itself:

```sql
-- Sanitising copy for attachment
sqlite3 pdf_extractor_v3.db ".backup sanitised.db"

sqlite3 sanitised.db <<SQL
UPDATE config SET value = '"[REDACTED]"' WHERE section = 'pdf_password';
UPDATE config SET value = json_set(value, '$.full_cookie', '[REDACTED]') WHERE section = 'ica';
UPDATE jwt_config SET value = '{"redacted": true}';
UPDATE tracking_files SET name = 'REDACTED.pdf', ref_number = 'REF', local_path = '', archive_path = '';
UPDATE extraction_logs SET content = replace(content, ref_number, 'REF-REDACTED');
VACUUM;
SQL
```

Attach `sanitised.db` instead of the original.

---

## Severity Assessment

Choose the severity that matches. See [Incident-Response.md](Incident-Response.md#severity-matrix) for definitions.

- **S1** — Data loss risk, or app unusable for a class of users.
- **S2** — Core workflow blocked; data safe.
- **S3** — Non-core feature broken; workaround exists.
- **S4** — Cosmetic.

Maintainer may reclassify after triage.

---

## Response SLA

| Severity | Acknowledgement | Fix ETA |
|---|---|---|
| S1 | 1 business hour | Same business day |
| S2 | 1 business day | Next release (2–4 weeks) |
| S3 | 1 business week | Best-effort in a future release |
| S4 | 1 business week | Backlogged |

---

## Bad Report Examples (and how to fix them)

### Bad
> "Upload doesn't work."

### Good
> **Version:** 3.0.0
> **Windows:** 11 Pro build 22631.4460
> **Steps:**
> 1. Launch the portable exe.
> 2. Open Scan page.
> 3. Click Upload Files.
> 4. Pick `Final Report - Jose Manalo.pdf` in the picker.
> 5. Observe the Scan page.
>
> **Expected:** the PDF appears in the Pending list.
> **Actual:** nothing happens. No toast, no progress row, no file in `Local Folder\`.
> **Frequency:** every time.
>
> **Diagnostics panel** (attached): shows `Last file pick: cancelled by user` even though I picked a file.
>
> **Backend log** (attached): no `POST /api/scan/upload` line after the click.

Second version leads to a fix in one attempt. First version leads to a week of "can you check X, can you check Y".

---

## What Happens Next

1. Maintainer acknowledges within SLA.
2. Triage → severity + label assigned.
3. Reproduction attempt on maintainer's machine.
4. If reproduced: fix branch off `main`, PR, review, merge.
5. Included in the next release (or a hotfix release for S1).
6. Reporter notified when the release is available.
7. Reporter re-tests, confirms, and closes the issue.

---

## Related

- [Troubleshooting.md](Troubleshooting.md) — self-serve first
- [Incident-Response.md](Incident-Response.md) — Sev 1 escalation
- [Feature-Request-Process.md](Feature-Request-Process.md) — for enhancements, not bugs
