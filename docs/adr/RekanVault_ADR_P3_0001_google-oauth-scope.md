### RV-DEC-P3-0001 — Google Drive OAuth Scope for Pilot

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 Google OAuth setup
- Context: Need to determine the Google OAuth permission scope for accessing user Google Drive files during internal pilot ingestion.
- Options:
  1. Internal pilot read-only scope (`https://www.googleapis.com/auth/drive.readonly`).
  2. Picker-driven file scope (`drive.file` + Google Picker API).
- Chosen option: Option 1 — `drive.readonly` scope for internal pilot.
- Why: Provides complete read access for recursive folder crawling, automatic document discovery, and incremental change tracking via `changes.list` without per-document picker friction.
- Impact: Environment variable `RV_GOOGLE_OAUTH_SCOPES` configured with `drive.readonly`. Public product deployment will evaluate `drive.file` + Google Picker API prior to public release.
- Reversal trigger: Transition from internal pilot to public SaaS launch requiring Google App Verification.
- Related ADR/tests: P3-T1, P3-T2, Google Drive adapter (`rekanvault/sources/google_drive.py`).
