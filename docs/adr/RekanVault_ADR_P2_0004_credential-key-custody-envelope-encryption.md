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

### Update — 2026-08-02 (gap found during P2 test-plan AC review)

The original decision defines 1 active + 1 previous key but does not
specify what happens when a key rotates *out* of the previous slot
(i.e. a third rotation occurs). As written, data still encrypted
under a dropped key becomes permanently undecryptable — this is a
silent data-loss path, not an intended behavior.

**Addition to Impact:** Key rotation must trigger a re-encryption
job that re-encrypts every row still using the outgoing "previous"
key under the new active key, before that key is removed from
`RV_CREDENTIAL_KEY_ACTIVE` / `RV_CREDENTIAL_KEY_PREVIOUS`. No
credential row may ever reference a key ID that is not one of the
two currently configured.

**Addition to To-dos (P2):** Implement rotation re-encryption job,
triggered manually or on rotation event, with a completion check
before the old key is retired.

**Addition to Test plan (P2-T8):** Verify re-encryption job clears
all rows off the outgoing key before it's dropped; verify no row
ever references an unconfigured key ID.
