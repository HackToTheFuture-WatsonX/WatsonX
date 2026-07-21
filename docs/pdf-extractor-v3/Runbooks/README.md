# Runbooks

Step-by-step, copy-pasteable procedures for common operational tasks. Written for a technically-comfortable operator (developer or IT admin) — not the day-to-day HR user.

Every runbook follows the same shape:

- **When to run it** — the trigger.
- **Preconditions** — what must already be true.
- **Steps** — numbered actions.
- **Verify** — how to confirm success.
- **Rollback** — how to undo.

---

## Registered Runbooks

| # | Runbook | When |
|---|---|---|
| [RB-01](RB-01-rebuild-and-release.md) | Rebuild and release a new version | Shipping a new build |
| [RB-02](RB-02-refresh-ica-cookies.md) | Refresh ICA session cookies | Bee returns "ICA unreachable" or cookies expired |
| [RB-03](RB-03-reset-config.md) | Reset a machine to factory config | Corrupted config, or preparing for hand-off |

---

## Adding a Runbook

- Number it sequentially (`RB-04`, `RB-05`, …).
- Name the file `RB-NN-short-slug.md`.
- Register it in the table above.
- Cross-link from [Troubleshooting.md](../Troubleshooting.md) or [Incident-Response.md](../Incident-Response.md) if it's incident-flavoured.
