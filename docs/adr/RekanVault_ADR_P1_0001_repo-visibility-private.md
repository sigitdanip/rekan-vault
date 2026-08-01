### RV-DEC-P1-0001 — Repository visibility mechanics: Private until P11 release candidate

- Phase: P1
- Status: Approved
- Owner: Sigit
- Date: 2026-08-01
- Decision required by: P1 creation
- Context: RekanVault is built as an internal knowledge system for PT Rekan Makmur Utama. SDLC Phase 1 requires locking the repository visibility policy for the build phase.
- Options:
  1. Make repository public or open-source during initial development.
  2. Keep repository private until P11 release candidate (defer public licensing).
- Chosen option: Option 2 — Repository stays strictly private on internal Git hosting until P11 release candidate.
- Why: Minimizes secret/privacy and licensing exposure during active core development. No open-source license file is needed during P1–P10.
- Impact: Repository access remains private. No public CI artifacts or public package publishing during P1–P10.
- Reversal trigger: If explicit approval for open-sourcing or external distribution is given prior to P11.
- Related ADR/tests: RV-DEC-0001 (P0 repo private decision).
