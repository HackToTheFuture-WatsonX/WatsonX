# Data Retention

Retention policies per data class. V3 does not enforce retention automatically — deletion is a deliberate operator action or scheduled maintenance job. This document names the recommended defaults; each deployment should adjust to its jurisdiction and controller policy.

---

## Data Classes

| Class | Location | Value | Recommended retention |
|---|---|---|---|
| PDF password | `config` (DB) | Auth material | Life of app install; delete on uninstall |
| Box JWT | `jwt_config` (DB) | Auth material | Life of app install; delete on uninstall |
| ICA cookie | `config.ica.full_cookie` (DB) | Auth material, short-lived | Overwritten by each new sign-in; no explicit retention |
| Sync targets (folder IDs, ICA team/chat) | `config` (DB) | Identifiers | Life of deployment |
| Tracking rows | `tracking_files` (DB) | Workflow state | Retained until file is deleted from Archive |
| Encrypted source PDFs (pre-extract) | `Local Folder\` | PII source | Until extracted (typically <1 day) |
| Archived source PDFs (post-extract) | `Local Folder\Archive\` | PII source | Business default: 90 days; adjust to policy |
| Word / Excel / JSON exports | `Local Folder\Extracted\<year>\…` | Extracted PII | Business default: 2 years for HR audit; adjust |
| Activity log rows | `extraction_logs` (DB) | Audit trail | Business default: 1 year online, then archive off-DB or delete |
| Backend log | `%TEMP%\pdf-extractor-v3-backend.log` | Debug only | One launch (auto-truncated) |
| Startup log | `%TEMP%\pdf-extractor-v3-startup.log` | Debug only | One launch (auto-truncated) |
| ICA log | `%APPDATA%\PDF Extractor V3\ica.log` | Debug + audit | Business default: 90 days; adjust |

---

## Retention Rationale

- **Archived source PDFs** — kept in case extraction needs to re-run (parser change, spot audit). 90 days covers typical audit cycles. Longer if regulated industry demands source-of-truth availability.
- **Exports** — the operational business asset. 2 years matches typical HR-record retention. Some jurisdictions require 6 years for financial-industry roles; adjust upward as needed.
- **Activity log** — 1 year covers a typical audit lookback. Older evidence should be archived externally (SIEM, immutable object storage) if you need multi-year traceability without ballooning the DB.
- **ICA log** — primarily debug aid; 90 days covers "the user reported an issue last week" scenarios. Do NOT retain longer than the cookie fingerprint is useful.

---

## How to Delete

### Trim old activity log rows

```sql
-- Close V3 first.
DELETE FROM extraction_logs
 WHERE occurred_at < date('now', '-1 year');
VACUUM;
```

Automate with a monthly scheduled task:

```bat
sqlite3 "%APPDATA%\PDF Extractor V3\pdf_extractor_v3.db" ^
    "DELETE FROM extraction_logs WHERE occurred_at < date('now', '-1 year'); VACUUM;"
```

### Trim old exports

```bat
:: Delete Word/Excel/JSON extracts from years past
forfiles /P "%APPDATA%\PDF Extractor V3\Local Folder\Extracted\Word Extracts" /D -730 /C "cmd /c echo @path"
```

Verify with `/C "cmd /c echo @path"`; replace with `/C "cmd /c del @path"` after confirming the list.

### Trim old archived source PDFs

```bat
forfiles /P "%APPDATA%\PDF Extractor V3\Local Folder\Archive" /S /M *.pdf /D -90 /C "cmd /c del @path"
```

### Trim the ICA log

```bat
del "%APPDATA%\PDF Extractor V3\ica.log"
```

Recreated on next ICA request.

---

## Subject-Erasure Requests

When a data subject exercises Article 17 (right to erasure) of GDPR (or equivalent):

1. Identify the case reference(s) associated with the subject.
2. Delete the source PDF from `Local Folder\Archive\<name>.pdf`.
3. Delete the export triplet under `Local Folder\Extracted\<year>\…\<ref>\`.
4. Delete rows from the DB:
   ```sql
   DELETE FROM tracking_files WHERE ref_number = '<ref>';
   DELETE FROM extraction_logs WHERE ref_number = '<ref>';
   VACUUM;
   ```
5. Confirm to the requester that the erasure is complete.

Consider a runbook per your deployment's frequency of such requests.

---

## Backup Retention

If you follow [Backup-and-Restore.md](Backup-and-Restore.md), your backup archive contains snapshots of the DB that may include data the subject asked to erase. Coordinate retention:

- Keep backups for the shortest interval consistent with your DR (Disaster Recovery) policy.
- On a subject-erasure request, either delete affected backups too, or restrict access to them per Article 18.

---

## Uninstall Path

Uninstalling V3 does **not** delete user data. A full-decommission checklist:

1. Uninstall via Windows Settings → Apps.
2. Delete `%APPDATA%\PDF Extractor V3\`.
3. Delete `%TEMP%\pdf-extractor-v3-*.log`.
4. Delete any exports the user copied elsewhere (Outlook attachments, personal folders).
5. If required by policy, sanitise the free space on the disk (`cipher /w:<letter>:` for basic wipe, or full BitLocker re-key).

---

## Related

- [Backup-and-Restore.md](Backup-and-Restore.md)
- [Compliance.md](Compliance.md)
- [Audit-Logs.md](Audit-Logs.md)
- [Security-Model.md](Security-Model.md)
