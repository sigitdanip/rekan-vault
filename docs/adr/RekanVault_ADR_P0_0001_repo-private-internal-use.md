### RV-DEC-0001 — Repository stays private; internal use only

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: Public release (not blocking P1 coding)
- Context: The SDLC plan requires a license/commercial model decision before public alpha. RekanVault's first deployment is entirely internal to PT Rekan Makmur Utama, with no current plan for external distribution.
- Options:
  1. Decide dual-license vs AGPL now, before any coding starts.
  2. Keep the repository private during build, defer the license decision until external distribution is actually planned.
- Chosen option: Option 2 — repository stays private, internal use only. No license decision made or needed at this time.
- Why: There is no current plan to distribute RekanVault outside the company. Deciding a license now would be premature and would not affect P1–P11 implementation work.
- Impact: No license file required yet. No public repository visibility. No contributor agreement needed.
- Reversal trigger: If external distribution, open-sourcing, or selling RekanVault to another organization becomes a real plan, this decision must be revisited before that release.
- Related ADR/tests: None yet.
