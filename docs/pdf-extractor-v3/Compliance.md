# Compliance

Regulatory considerations for PDF Extractor V3. Written for enterprise deployments that must satisfy GDPR-adjacent obligations. Not a legal opinion — validate against your own counsel.

---

## Scope of Data Processed

PDF Extractor V3 processes **personal data** in the sense of GDPR Article 4:

- Subject full name (as reported in the vendor PDF).
- Employment history (employer names, dates, verification status).
- Professional reference statements.
- Database-check results (adverse media, sanctions, bankruptcy, credit, directorships, litigation, licences, social media).
- Government/case reference numbers.

All of this data is transported and stored in three forms:
1. Encrypted PDFs on Box (before processing).
2. Structured Word / Excel / JSON exports in `Local Folder/Extracted/`.
3. Rows in the `extraction_logs` and `tracking_files` tables of `pdf_extractor_v3.db`.

---

## Legal Basis (typical enterprise deployment)

The controller (the employer running background checks) typically relies on:

- **Article 6(1)(b)** — necessity for a contract (employment offer).
- **Article 6(1)(f)** — legitimate interest (fraud prevention, regulated employment).
- **Article 6(1)(c)** — legal obligation (regulated industries like financial services).

V3 itself is a **processor** — a tool that acts on the controller's instructions to transform the vendor's data into local exports. V3 does not initiate any processing autonomously.

---

## Data Minimisation

V3 stores only what the workflow requires:

| Data | Purpose | Justification |
|---|---|---|
| Full subject name | Needed for identification, HR case linking | Data minimisation preserved |
| Case reference | Primary key for HR workflow tracking | Business necessity |
| Employment / reference / db-check results | The value V3 delivers | Purpose of processing |
| Source PDFs | Retained to allow re-extraction if the parser changes | Business necessity, bounded retention |
| Activity log rows | Audit trail per Article 5(2) — accountability | Legal necessity |

V3 does not store:

- Raw vendor API responses beyond what's in the PDF.
- Chat transcripts with Bee server-side (only in the client store).
- IP addresses / operator identifiers beyond the Windows account context.
- Telemetry, analytics, or any phone-home data.

---

## Retention

See [Data-Retention.md](Data-Retention.md) for exact policies. Summary:

| Data class | Retention within V3 | Deletion mechanism |
|---|---|---|
| Encrypted source PDFs (pre-extraction) | Until extracted | Automatic move to Archive on success |
| Archived source PDFs (post-extraction) | Operator-defined (default: indefinite) | Manual delete |
| Exports (Word/Excel/JSON) | Operator-defined | Manual delete |
| Activity log rows | Operator-defined | Manual `DELETE FROM extraction_logs` |
| Config incl. credentials | Until Settings reset or app uninstall | Manual delete of `pdf_extractor_v3.db` |

V3 provides no automatic retention deletion. Enterprise deployments should either:

- Set a scheduled task that trims `extraction_logs` and old export folders per policy.
- Run [RB-03 — Reset Config](Runbooks/RB-03-reset-config.md) at end-of-project.

---

## Data Subject Rights

Where GDPR (or equivalent) applies:

| Right | How to satisfy |
|---|---|
| **Access** (Art. 15) | Locate the case reference, open the Word/JSON export, provide it |
| **Rectification** (Art. 16) | Re-run extraction from a corrected source PDF; delete the old export |
| **Erasure** (Art. 17) | Delete the case's row from `tracking_files`, remove the source PDF from `Archive/`, remove the three exports under `Extracted/`, delete matching rows from `extraction_logs` |
| **Restriction** (Art. 18) | No V3-native mechanism; operationally, don't extract that file |
| **Portability** (Art. 20) | Provide the JSON export — machine-readable structured format |
| **Objection** (Art. 21) | Out of V3's scope — controller decision |

There is no in-app "delete this subject" button; a subject-erasure request is a maintenance operation (typically for the IT admin) touching two locations:

1. `Local Folder\Archive\<name>.pdf` — delete.
2. `Local Folder\Extracted\<year>\...\<ref>\...` — delete the three files.
3. `pdf_extractor_v3.db`:
   ```sql
   DELETE FROM tracking_files WHERE ref_number = '<ref>';
   DELETE FROM extraction_logs WHERE ref_number = '<ref>';
   ```

Consider a runbook if this is a routine operation for your deployment.

---

## Cross-Border Transfer

V3 sends personal data to two external services:

- **IBM Box** — receives PDFs and outputs. Ensure your Box tenancy is provisioned in a region that satisfies your data-transfer requirements (e.g. EU-based for GDPR).
- **IBM Consulting Advantage** — receives chat prompts. Enable ICA only if your legal basis extends to sharing the prompt content (which may include names).

The Bee system prompt is content-only (no PII) and is safe to send. User chat messages may contain PII if the user includes it — controllers should train users accordingly.

---

## Encryption

- **In transit** — TLS 1.2+ enforced by Box and ICA endpoints.
- **At rest on Box** — Box's server-side encryption applies.
- **At rest locally** — V3 does NOT encrypt `pdf_extractor_v3.db` or the exports on disk. Rely on:
  - Windows account file permissions (default).
  - Disk-level encryption (BitLocker, recommended for enterprise deployments).

An in-app encryption layer (DPAPI-wrapped credentials, encrypted DB) is on the [Roadmap.md](Roadmap.md).

---

## Data Processing Agreement

If your controller-processor relationship requires a DPA:

- V3 is a locally-run tool. There is no vendor to sign a DPA with for V3 itself.
- The Box and ICA relationships require their respective DPAs (via IBM).
- Consider documenting internally that V3 is deployed as an in-house processing tool with defined access controls.

---

## Audit

- The `extraction_logs` table provides a full per-user audit trail.
- Backend logs at `%TEMP%\pdf-extractor-v3-backend.log` provide operational detail (retained one launch).
- ICA logs at `%APPDATA%\PDF Extractor V3\ica.log` provide the complete chat request history.

Preserve these for the retention period your policy demands.

See [Audit-Logs.md](Audit-Logs.md) for detail.

---

## Deletion on Decommission

When retiring an operator machine:

1. Backup relevant history externally per your controller policy.
2. Uninstall V3 (does not delete user data).
3. Delete `%APPDATA%\PDF Extractor V3\` completely.
4. Delete `%TEMP%\pdf-extractor-v3-*.log`.
5. Zero-fill or full-disk-wipe the drive if the data classification requires it.

---

## Related

- [Security-Model.md](Security-Model.md) — controls in place
- [Data-Retention.md](Data-Retention.md) — retention policy details
- [Audit-Logs.md](Audit-Logs.md) — what's retained for audit
- [Data-Flow.md](Data-Flow.md) — where data goes
