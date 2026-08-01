### RV-DEC-P2-0004 — Security: Credential key custody with runtime envelope encryption

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 credential repository implementation
- Context: Source connectors (Google Drive, Notion) require storing OAuth refresh tokens and API tokens in PostgreSQL. SDLC Phase 2 requires establishing key custody and rotation.
- Options:
  1. Single static secret key stored in environment variables without rotation support.
  2. Runtime envelope encryption (AES-GCM) supporting 1 active key ID and 1 previous key ID stored in deployment secrets.
- Chosen option: Option 2 — Runtime envelope encryption (`RV_CREDENTIAL_KEY_ACTIVE`, `RV_CREDENTIAL_KEY_PREVIOUS`).
- Why: Allows workers and API handlers to decrypt tokens at runtime while enabling zero-downtime key rotation without re-authenticating connected sources.
- Impact: `credentials` table stores ciphertext, key ID, and IV. Encrypted credential repository inspects key ID and falls back to previous key during rotation.
- Reversal trigger: Shift to external Key Management Service (KMS) in enterprise deployment phase.
- Related ADR/tests: P2 credential encryption test plan.
