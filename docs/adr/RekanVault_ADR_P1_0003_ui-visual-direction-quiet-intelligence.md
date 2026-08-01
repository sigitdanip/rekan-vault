### RV-DEC-P1-0003 — UI visual direction: Quiet intelligence workspace baseline

- Phase: P1
- Status: Approved
- Owner: Sigit
- Date: 2026-08-01
- Decision required by: P1 web shell creation
- Context: RekanVault's frontend requires a cohesive design language and component token strategy established during Phase 1.
- Options:
  1. Generic light/utility dashboard theme.
  2. Quiet intelligence workspace: dense but calm, desktop-first, dark mode baseline with subtle glassmorphism and modern typography.
- Chosen option: Option 2 — Quiet intelligence workspace (`apps/web/src/app/globals.css`).
- Why: Delivers a high-density, calm, premium user experience tailored for enterprise document analysis and evidence synthesis without visual clutter.
- Impact: Dark background (`hsl(222 47% 7%)`), Inter typography, `.glass-panel` utilities with subtle backdrop blurs, and Tailwind CSS tokens enforced in `apps/web`.
- Reversal trigger: User feedback during pilot phase (P11) requesting high-contrast light mode alternative.
- Related ADR/tests: RV-DEC-0003 (English primary UI).
