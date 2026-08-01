### RV-DEC-0002 — Pilot corpus scope: 1 Drive folder tree + 1 Notion root page with nested databases

- Phase: P0 (scope), enforced at P3 (Google Drive and Notion Lifecycle)
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P3 sandbox test
- Context: The Product Build Plan recommends one bounded Drive root and one bounded Notion root for the first pilot, to keep lifecycle-convergence testing (create/rename/move/trash/delete/permission-loss) tractable. Sigit's initial proposal was broader: one large Drive folder tree ~4 levels deep, plus a Notion workspace with multiple scattered pages and multiple databases.
- Options:
  1. Full scope as originally proposed: 4-level Drive tree + multiple scattered Notion pages/databases.
  2. Bounded scope: same Drive tree, but Notion narrowed to one top-level page with all databases nested inside it as children.
- Chosen option: Option 2. Drive: one folder tree, ~4 levels deep. Notion: one top-level page, with multiple databases nested inside that single page (not scattered across the workspace).
- Why: Notion's API only grants access at the page level — an integration must be explicitly shared with a top-level page, and that access cascades to all nested children. Sharing one top-level page that contains all target databases is both the only practical way the API works and keeps the connector's permission/lifecycle test surface bounded to one root, matching the plan's recommendation.
- Impact: Simplifies Notion integration setup in P3 to a single page-share action. Drive side remains as originally scoped (4 levels deep, which Drive's API handles natively via recursion). Keeps P3-GATE lifecycle testing scoped to one Drive root and one Notion root, as the plan intends.
- Reversal trigger: If pilot testing surfaces a need for multiple disconnected Notion roots (e.g. content that cannot be reorganized under one parent page), this decision should be revisited and Notion's multi-root support (already designed for in the connector contract) can be enabled.
- Related ADR/tests: P3-GATE lifecycle convergence tests (SDLC plan, Phase 3 test plan).
