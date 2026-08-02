### RV-DEC-P3-0002 — Notion Authentication Model for Pilot

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 Notion integration onboarding
- Context: Need to select the authentication mechanism for connecting RekanVault to Notion workspaces.
- Options:
  1. Internal Integration Token (`secret_...`) for pilot onboarding.
  2. Public OAuth 2.0 Web Flow (`https://api.notion.com/v1/oauth/authorize`).
- Chosen option: Option 1 — Internal Integration Token.
- Why: Eliminates OAuth redirect complexity and external callback domain requirements during pilot testing, while ensuring strict access isolation to pages explicitly shared with the integration.
- Impact: Token stored encrypted via `RV_NOTION_INTEGRATION_TOKEN`. Public OAuth deferred to multi-tenant public release.
- Reversal trigger: Multi-tenant SaaS release requiring self-serve non-admin user onboarding.
- Related ADR/tests: P3-T1, P3-T2, Notion adapter (`rekanvault/sources/notion.py`).
