### RV-DEC-0003 — UI language: English primary, Indonesian-ready strings

- Phase: P0 (decision), enforced starting P1 design tokens, implemented P3 (`next-intl` introduced)
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P1 design tokens
- Context: The Product Build Plan's default recommendation was Indonesian primary, English content-safe. Sigit's team operates primarily in English for this product's UI.
- Options:
  1. Indonesian primary, English secondary (original plan default).
  2. English primary, Indonesian secondary.
- Chosen option: Option 2 — English primary. All UI strings are still prepared for both English and Indonesian from the start (via `next-intl`), so Indonesian support is not a later retrofit.
- Why: Matches the actual working language preference of the team using RekanVault day to day.
- Impact: Default locale in `next-intl` config is `en`. Copy, navigation labels, and error messages are authored in English first, with Indonesian translations maintained in parallel rather than deferred.
- Reversal trigger: None anticipated; would only change if primary user base shifts.
- Related ADR/tests: P8 workspace UI component tests (message catalog coverage for both locales).
