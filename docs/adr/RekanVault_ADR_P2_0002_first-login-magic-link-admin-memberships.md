### RV-DEC-P2-0002 — Authentication: Email magic link login with administrator-created memberships

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 authentication & UI shell
- Context: Phase 2 establishes user identity, authentication JWTs, and workspace memberships.
- Options:
  1. Password-based authentication (email + password).
  2. Google/SSO OAuth-only login.
  3. Email magic link authentication paired with administrator-created workspace memberships.
- Chosen option: Option 3 — Email magic link authentication via Supabase Auth + admin membership provisioning.
- Why: Eliminates password management overhead and credential security risks while maintaining strict administrative control over workspace access.
- Impact: Supabase Auth handles magic link generation/verification. Users cannot self-register workspaces without an administrator invitation/membership grant (`memberships` table).
- Reversal trigger: Requirement for enterprise SAML/SSO integration in later phase (P10+).
- Related ADR/tests: RV-DEC-0010 (Supabase Auth).
