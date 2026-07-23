# Versioning Policy

PDF Extractor V3 follows **Semantic Versioning 2.0.0** with the additional constraint that all three version strings (backend, frontend, electron) must move in lock-step.

Format: `MAJOR.MINOR.PATCH`.

---

## Version Sources

All three must match. Where they live:

- `PDF Extractor V3\backend\main.py` → `APP_VERSION = "3.0.0"`.
- `PDF Extractor V3\electron\package.json` → `"version": "3.0.0"`.
- `PDF Extractor V3\frontend\package.json` → `"version": "3.0.0"`.

The `/api/health` endpoint returns the backend's `APP_VERSION`. Distributable filenames use the electron `package.json` version. On every release, all three are bumped together. See [RB-01](Runbooks/RB-01-rebuild-and-release.md).

---

## Increment Rules

### MAJOR — bump when

- Data schema breaks in a way that requires a migration function or manual intervention.
- A supported endpoint URL or SocketIO event name changes (renamed, removed, or its response shape changed).
- The distributable format changes (e.g. installer replaces portable, or macOS becomes primary).
- ICA / Box authentication mechanism changes such that existing operators must re-enrol.

Examples of MAJOR-worthy changes:
- Add row-level encryption to `pdf_extractor_v3.db` (requires migration).
- Rename `POST /api/extract/run` to `POST /api/pipeline/execute`.
- Drop Windows 10 support in favour of Windows 11.

### MINOR — bump when

- New features are added while preserving backwards compatibility.
- New endpoints, new UI pages, new SocketIO events.
- New optional config fields (with sensible defaults).
- Non-breaking dependency upgrades.

Examples:
- Add an "Auto-sync" scheduler.
- Add a Retry action to the Extract page.
- Add support for a new PDF template alongside the existing one.
- Add a new activity-log category.

### PATCH — bump when

- Bug fixes.
- Documentation-only changes that ship with a build.
- Performance improvements with no behaviour change.
- Security fixes that don't alter contracts.

Examples:
- Fix an off-by-one in the Insights weekly chart.
- Fix a race in Socket.IO emit ordering.
- Add a hidden import to `backend.spec` to unstick a missing-module error.

---

## Pre-release Suffixes

For internal dogfooding and beta rings:

- `3.1.0-rc.1`, `3.1.0-rc.2` — release candidates.
- `3.1.0-beta.1` — user-testable but expected to change.
- `3.1.0-alpha.1` — internal experiments.

Pre-release builds ship as separate exe files with the suffix in the filename: `PDF-Extractor-V3-Portable-3.1.0-rc.1.exe`.

---

## What Constitutes a Break

Anchor concept: any change that requires an existing operator to *do something* to keep working is a MAJOR-level break.

| Change | Break? |
|---|---|
| Rename a table | Yes |
| Add a nullable column | No |
| Add a required column with no default | Yes (unless backfilled at startup) |
| Change the shape of `/api/settings` response | Depends on which field |
| Add a new field | No |
| Remove a field | Yes |
| Change the value semantics of a field | Yes |
| Rename a SocketIO event | Yes |
| Add a new SocketIO event | No |
| Change the JSON shape of an event payload | Depends; usually yes |
| Change the extraction output filename format | Yes (downstream jobs may parse names) |
| Change a config default | Depends; usually no |

When in doubt, treat as MAJOR and document loudly in [Release-Notes.md](Release-Notes.md).

---

## Compatibility Windows

V3 does not maintain multiple parallel MAJOR releases. Once a 4.0 exists, 3.x is on maintenance:

- **3.x maintenance** — security fixes for **12 months** after 4.0 release (PATCH-only).
- **3.x deprecation** — no further changes; users are asked to migrate to 4.x.

See [EOL-Policy.md](EOL-Policy.md).

---

## Versioning the API

Because the backend is bound to `127.0.0.1` and only ever paired with a specific frontend build (same install), API versioning is *not* URL-prefixed. `POST /api/scan/upload` is not `POST /api/v1/scan/upload`.

If in a future major we anticipate parallel API surfaces, prefix them then. Meanwhile, one bundle owns one version of the API.

---

## Versioning the Data Directory

The user data directory is `%APPDATA%\PDF Extractor V3\` — the `V3` in the path is deliberately the MAJOR. When V4 ships:

- Its user data goes to `%APPDATA%\PDF Extractor V4\`, isolated from V3.
- Migration between them is an explicit operator action, not automatic.
- V3 and V4 can coexist on the same machine without interfering.

---

## Tag Format

Git tags: `vMAJOR.MINOR.PATCH` (e.g. `v3.1.0`, `v3.0.1-rc.1`).

`git describe --tags` on a release commit returns exactly the tag.

---

## Related

- [Release-Notes.md](Release-Notes.md) — cumulative changelog
- [Roadmap.md](Roadmap.md) — proposed future versions
- [EOL-Policy.md](EOL-Policy.md) — deprecation timeline
- [Runbooks/RB-01](Runbooks/RB-01-rebuild-and-release.md) — release procedure
