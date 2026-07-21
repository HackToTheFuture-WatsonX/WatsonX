# End-of-Life Policy

When and how PDF Extractor V3 (or a specific MAJOR of it) stops receiving updates.

---

## Support Tiers

At any given moment, one release train is **current** and at most one is **maintenance-only**:

| Tier | What happens |
|---|---|
| **Current** (latest MAJOR) | New features, bug fixes, security fixes |
| **Maintenance** (previous MAJOR) | Security fixes only; no new features; no PATCH releases unless critical |
| **End of Life** | No updates. Users are asked to migrate |

Example timeline: when 4.0 releases, 3.x moves to maintenance for 12 months, then to EOL. 4.x is current from that point.

---

## Support Windows

- **Maintenance** — **12 months** after the next MAJOR ships.
- **EOL** — thereafter.

These are targets, not guarantees. A critical vulnerability in an EOL train may prompt an emergency patch at the maintainer's discretion.

---

## What Triggers a New MAJOR

See [Versioning-Policy.md](Versioning-Policy.md#major--bump-when) for the definitive list. Reprise:

- Schema-breaking DB changes.
- API or SocketIO event contract removals.
- Windows-version support drops.
- Auth mechanism overhauls.

Each of these justifies MAJOR and starts a fresh support window.

---

## What EOL Means for Users

When a MAJOR reaches EOL:

- No further installers are built for that MAJOR.
- Bug reports on that MAJOR are closed with `wontfix / EOL`.
- The maintainer publishes a migration guide to the current MAJOR.
- The old MAJOR remains **runnable** — it doesn't self-destruct — but it will not receive fixes.

Users can continue running an EOL version if their environment forbids upgrading. They accept the risk. `pdf_extractor_v3.db` data is not affected by version transitions of the app binary itself; upgrading is generally low-risk.

---

## Migration Path (V3 → V4, when V4 exists)

Anticipated shape of a MAJOR migration:

1. Publish V4 alongside V3.
2. Publish a migration doc explaining what changed and any data-shape considerations.
3. V4 uses a fresh data directory (`%APPDATA%\PDF Extractor V4\`) so the two can coexist.
4. Provide an optional migration script (or in-app "Import from V3" button) if the shift is small enough.
5. Operators run V4 in parallel for a period; when confident, they retire V3.

There is no forced migration. The maintainer's role is to make the current MAJOR compelling enough that operators upgrade voluntarily.

---

## EOL of the Whole Product

If V3 (or its successor) is retired entirely — e.g. superseded by a different tool inside IBM's ecosystem:

1. The maintainer announces the sunset date at least 90 days in advance.
2. A final release fixes any known critical bugs.
3. The GitHub repo is archived (read-only).
4. Existing installations continue to work as long as Box and ICA continue to accept their traffic. When either vendor changes contracts (see [Maintenance-Plan.md](Maintenance-Plan.md#handling-vendor-behaviour-changes)), the app is likely to break — that's the effective end.
5. Data in `%APPDATA%\PDF Extractor V3\` remains readable via any SQLite tool.

---

## Related

- [Versioning-Policy.md](Versioning-Policy.md) — what MAJOR / MINOR / PATCH mean
- [Roadmap.md](Roadmap.md) — proposed future releases
- [Maintenance-Plan.md](Maintenance-Plan.md) — ongoing hygiene
- [Deployment-Guide.md](Deployment-Guide.md) — install/uninstall procedures
