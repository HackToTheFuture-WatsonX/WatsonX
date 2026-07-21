# Roadmap

Prioritised list of planned work. Not a commitment schedule — items shift based on user reports and available capacity.

Grouped by target release. Bumps to specific versions are not promised until they land on `main`.

---

## Near-term — Target 3.1.x

Bug-fix and quality-of-life focus. No breaking changes.

- **Auto-sync scheduler** — wire `settings.sync.auto_sync_enabled` and `auto_sync_interval_minutes` to a background timer that runs `sync_box_to_local` on schedule. Currently the config fields exist but do nothing.
- **Signed installer + portable** — code-signing certificate + `electron-builder` `sign` config. Eliminates the SmartScreen warning.
- **Retry failed extractions in batch** — a "Retry Failed" action on the Extract page that re-runs only rows whose last activity-log entry starts with `FAILED:`.
- **Export activity logs to CSV** — button on the Logs page.
- **HTTP session reuse to Box** — configure `boxsdk` to reuse a session, cutting per-request TLS overhead.
- **ICA log rotation** — file-size-based rotation at 10 MB via `RotatingFileHandler`.
- **Diagnostics panel on Sync + Extract pages** — same pattern as Scan.
- **"Copy diagnostics bundle to clipboard"** — one button that gathers version, resolved API base, backend log path, and last-fetch state into a bug-report-ready block.

---

## Mid-term — Target 3.2.x

Feature additions consistent with the V3 architecture.

- **Parallel extraction** — thread-pool over the pending set, bounded by a UI setting (default: 2). Estimated 2×–4× throughput on 4-core machines. Requires careful synchronisation on the tracking DB and event stream.
- **Chat-triggered file open** — extend `_skill_open_report` to accept `"open the JSON for BG-2026-01234"` as a single command.
- **Insights: per-day extraction throughput chart** — daily counts over the last 90 days.
- **Configurable retention** — a Settings section that runs the retention SQL and disk cleanup per policy.
- **Bee persona reload without restart** — `POST /api/settings/init/ica/reload` that re-reads `bee_prompt.md` and re-primes.
- **Optional local-only mode** — hide Box UI entirely when no JWT is configured, for machines that only Upload + Extract.

---

## Longer-term — Target 3.x / 4.0

Larger items that may cross MAJOR.

- **Encryption at rest** — DPAPI-wrapped credential columns, or full SQLite encryption via SQLCipher. Migration required.
- **macOS + Linux builds** — additional `electron-builder` targets. PyInstaller needs per-platform builds.
- **Multi-user server mode** — turn V3 into a small HTTP service for team-shared processing. Requires auth, RBAC, and a redesign of the data-directory model. Likely V4.
- **Structured extraction plugins** — replaceable `pdf_text_extractor` implementations per vendor template. Currently the parser is calibrated to one vendor.
- **OCR fallback** — PyTesseract integration for scanned PDFs. Weight cost tradeoff.
- **Signed and reproducible builds** — deterministic PyInstaller output + signed release manifest for supply-chain verification.
- **Automated test suite** — pytest for backend, Playwright for the packaged UI. Precondition for any of the larger items above.
- **CI on GitHub Actions** — runs the build + smoke tests on every PR. Skeleton in [CI-CD.md](CI-CD.md).

---

## Explicitly Not Planned

Consistent with [Feature-Scope.md](Feature-Scope.md#out-of-scope-deliberate). If any of these become planned, they earn an ADR first.

- Report editing / redlining.
- Non-Box source integrations.
- Push notifications.
- Mobile client.
- Multi-tenant SaaS.

---

## How Items Move

- **User request** → filed via [Feature-Request-Process.md](Feature-Request-Process.md).
- **Bug report** with feature implication → discussed with reporter; if broad enough, promoted here.
- **Maintainer initiative** → posted here first for visibility, then implemented.

Items on this list without a target release are candidates. Items with a target may still slip — a slip is not a commitment break.

---

## Related

- [Feature-Scope.md](Feature-Scope.md) — what's in the current shipping product
- [Release-Notes.md](Release-Notes.md) — what's actually shipped
- [Versioning-Policy.md](Versioning-Policy.md) — what a MAJOR bump means
- [EOL-Policy.md](EOL-Policy.md) — when things get retired
