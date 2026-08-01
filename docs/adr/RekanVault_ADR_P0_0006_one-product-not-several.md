### RV-DEC-0006 — RekanVault is one product, not several

- Phase: P0
- Status: Approved
- Owner: Imi (Product Build Plan owner); ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P0 (repository structure depends on this)
- Context: RekanVault spans source connectors, retrieval, memory, graph, context assembly, a human workspace, and SkillTree. These could be built as separate products/services or as one integrated product with internal module boundaries.
- Options:
  1. Split into separate products (e.g. a standalone RAG service, a standalone memory service).
  2. One product, one repository, one deployment, with internal modular boundaries.
- Chosen option: Option 2.
- Why: Source evidence, memory, graph, context, UI, and SkillTree all feed one continuous user outcome — splitting them would force premature network boundaries and duplicate identity/permission systems across services.
- Impact: One repository (`rekan-vault`), one deployment model, one authorization system, one canonical document identity, as defined in Product Build Plan section 1.
- Reversal trigger: Only if a specific module (e.g. retrieval) needs independent scaling that the modular monolith cannot support — to be evaluated with real usage data, not upfront.
- Related ADR/tests: RV-DEC-0007 (modular monolith architecture).
