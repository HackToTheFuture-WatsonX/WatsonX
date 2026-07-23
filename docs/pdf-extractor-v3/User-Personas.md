# User Personas

Concise persona sheets. Each names the goal V3 exists to serve for that role, the frustrations V3 removes, and the surfaces they touch most.

---

## P1 — HR Operations Analyst (primary)

**Alias:** "Priya"
**Role:** Day-to-day background-check intake and result publishing.
**Volume:** 10–40 reports per business day.
**Tech comfort:** Fluent in Excel and Outlook; not a developer.

### Goals

- Turn overnight vendor PDFs into structured, sharable outputs before the 10 a.m. stand-up.
- Answer stakeholder questions about specific candidates without hunting file paths.
- Keep an audit trail of what was processed and when.

### Frustrations (that V3 removes)

- Re-typing PDF fields into spreadsheets by hand.
- Encrypted PDFs blocking simple copy-paste.
- Losing track of which files have been processed already.
- Manually uploading exports back into Box for downstream teams.

### V3 Surfaces Used

- **Sync** — daily driver.
- **Extract** — clicks Run Extraction once a day.
- **View** — opens Word exports for stakeholder review.
- **Chat (Bee)** — quick lookups by name or reference.

### Success Signal

Zero manual data-entry. The Logs page confirms every intake with a green Info badge.

---

## P2 — Compliance Reviewer (secondary)

**Alias:** "Adam"
**Role:** Periodic audit and QA sampling of processed reports.
**Volume:** 5–10 sampled records per audit cycle (weekly).
**Tech comfort:** Comfortable reading logs and structured JSON.

### Goals

- Verify that a randomly sampled processed report matches its source.
- Trace an activity-log entry back to the source PDF and its exports.
- Confirm that failed extractions were addressed (not silently swept).

### Frustrations (that V3 removes)

- No unified log surface — used to hunt across multiple `.log` files.
- No easy way to correlate a processed record with its Box location.

### V3 Surfaces Used

- **Logs** — filters by period and level.
- **Insights** — completion counters and charts.
- **View** — opens exports side-by-side.
- **Chat (Bee)** — `look up <ref>` for structured summary.

### Success Signal

Every sampled row cross-references from log → export → archived source without a single manual file search.

---

## P3 — Operations Manager (tertiary)

**Alias:** "Nadia"
**Role:** Tracks team throughput and SLA adherence.
**Volume:** Reads the dashboard weekly.
**Tech comfort:** Non-technical; wants a chart, not a query.

### Goals

- See how many reports were processed this week vs last week.
- Know whether any recent runs failed.
- Spot bottlenecks (Pending backlog growing?).

### V3 Surfaces Used

- **Insights** exclusively.

### Success Signal

Single glance gives a truthful pass/fail read on the week's ops.

---

## P4 — Power User / Analyst-with-Curiosity (occasional)

**Alias:** "Miguel"
**Role:** HR analyst who prefers keyboard-driven workflows.
**Volume:** Ad-hoc.
**Tech comfort:** Comfortable with markdown and JSON.

### Goals

- Trigger the pipeline from a single chat surface.
- Search across all extracted reports for a specific attribute.
- Open the raw JSON to write a one-off pivot in Excel.

### V3 Surfaces Used

- **Chat (Bee)** — primary; issues `sync`, `extract`, `look up`, `logs this month`.
- **View** — occasional JSON open.

### Success Signal

Complete a full sync/extract/lookup cycle without ever leaving the chat bubble.

---

## P5 — IT Administrator (setup only)

**Alias:** "Sam"
**Role:** Provisions new operator machines; does not do daily ops.
**Volume:** A few per quarter.
**Tech comfort:** Windows admin; comfortable with Box developer console.

### Goals

- Get a new machine to `Ready` status in under 20 minutes.
- Confirm all credentials are stored securely.
- Have a repeatable checklist to follow.

### V3 Surfaces Used

- **Settings** exclusively — enters credentials, uploads JWT, runs both connection tests, initializes ICA system prompt.

### Success Signal

The Settings status widget shows `Box: configured ✓` and `ICA: primed ✓`.

---

## P6 — Developer (internal, not an end-user)

**Alias:** "Jules"
**Role:** Maintains and extends V3.
**V3 Surfaces:** Source tree + the FastAPI `/docs` route for interactive endpoint testing.

Docs targeted at this persona: [Developer-Onboarding.md](Developer-Onboarding.md), [Codebase-Structure.md](Codebase-Structure.md), [API-Documentation.md](API-Documentation.md).

---

## Persona → Documentation Map

| Persona | First read |
|---|---|
| P1 (Priya) | [Quickstart.md](Quickstart.md), [User-Guide.md](User-Guide.md) |
| P2 (Adam) | [Audit-Logs.md](Audit-Logs.md), [Logging.md](Logging.md) |
| P3 (Nadia) | [User-Guide.md#insights](User-Guide.md), [Performance-Benchmarks.md](Performance-Benchmarks.md) |
| P4 (Miguel) | [User-Guide.md#chat-with-bee](User-Guide.md), [API-Documentation.md](API-Documentation.md) |
| P5 (Sam) | [Deployment-Guide.md](Deployment-Guide.md), [Environment-Setup.md](Environment-Setup.md) |
| P6 (Jules) | [Developer-Onboarding.md](Developer-Onboarding.md) |
