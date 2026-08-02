### RV-DEC-P3-0003 — Connector Reconciliation and Safety Polling Cadence

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 background job scheduler
- Context: Need to define polling intervals for incremental changes, safety polling, and full inventory reconciliation.
- Options:
  1. Balanced Cadence: Incremental Drive sync 3 min; Notion safety poll 5 min; full reconciliation daily.
  2. High-frequency sync: Incremental Drive/Notion sync 1 min; full reconciliation 6-hourly.
  3. Webhook-only: No periodic short polling; full reconciliation daily.
- Chosen option: Option 1 — Balanced Cadence (Drive 3m, Notion 5m, Daily full recon).
- Why: Fits comfortably within ~8 GB VPS resource constraints, stays well under provider API quotas (Google 20,000 req/100s, Notion 3 req/s), and maintains sub-5-minute sync freshness for active documents.
- Impact: Worker scheduler configures 3-minute Drive `changes.list` job, 5-minute Notion safety poll job, and 02:00 UTC daily reconciliation job.
- Reversal trigger: High sync latency feedback or API quota throttling during pilot load.
- Related ADR/tests: P3-T3, P3-T7, worker job scheduler (`apps/worker/`).
