### RV-DEC-0014 — Redaction policy: content-masking for Confidential, full existence-hiding for Restricted

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P2 schema (permission model), enforced throughout P4 (Search), P6 (Graph), P7 (Ask/Answer)
- Context: RV-DEC-0005 locked four classification labels (Public, Internal, Confidential, Restricted) but left their actual enforcement behavior undefined. Classification is a permission signal (SDLC plan section 3.3, "product behavior policy") that governs what unauthorized users can see across search, graph traversal, logging, export, and grounded-answer citations. Two fundamentally different protection strengths exist: content-masking (existence is visible, content is hidden until access is granted) and full existence-hiding (an unauthorized user cannot tell the object exists at all — no leak via result counts, graph gaps, autocomplete, or error-message differences).

  Full existence-hiding is materially harder to build correctly than content-masking: it must be enforced consistently everywhere a hint could leak (search result counts, graph neighborhood gaps, entity-name autocomplete, "not found" vs "permission denied" error responses), not just at the obvious content-serving point.

- Options:
  1. Apply the same protection strength (either masking or full hiding) uniformly across Confidential and Restricted.
  2. Graduated protection: Confidential is content-masked (existence visible, content hidden); Restricted is fully hidden (existence itself not revealed) — reserving the harder-to-build guarantee for the smallest, most sensitive tier.
- Chosen option: Option 2.
- Why: Matches how real corporate classification systems typically behave — most sensitive-but-normal business content (e.g. a restructuring plan, a client contract) benefits from being discoverable-but-gated (masking), so authorized people know what to request access to. The smallest, highest-sensitivity category (e.g. HR investigations, board-level matters) needs the stronger existence-hiding guarantee. Applying full existence-hiding everywhere would be unnecessarily complex to build correctly and would remove the practical benefit of "knowing something exists so you can request access" for content that doesn't need that level of protection.
- Impact:
  - **Public / Internal**: fully visible to any authenticated workspace member, no masking or hiding logic needed.
  - **Confidential**: existence is visible in search results, graph neighborhoods, and entity references (e.g. "1 confidential document matched — request access"), but content, chunks, and citation text are never served to an unauthorized role. Authorized roles see full content.
  - **Restricted**: fully hidden from unauthorized roles — must not appear in search result counts, must not create a visible gap or dead-end in graph traversal, must not surface via autocomplete/entity suggestions, and permission-denied vs. not-found error responses must be indistinguishable to avoid confirming existence. Authorized roles see full content.
  - This must be enforced at the permission-check-before-serialization point already required by product principle 10 and section 19.3 ("Authorization is evaluated before content serialization"), but for Restricted specifically, enforcement must extend to aggregate/derived surfaces (counts, graph structure, suggestions) — not just direct content responses.
  - P4 (Search) must implement masked vs. fully-excluded result handling as two distinct code paths, not one.
  - P6 (Graph) must ensure Restricted nodes/edges produce no visible trace (no dangling reference, no "1 hidden connection" indicator) in bounded neighborhood views, while Confidential nodes can show as a masked placeholder.
  - P7 (Ask/Answer) must never cite a Restricted source to an unauthorized requester, and must not cite a Confidential source's content (though acknowledging one exists, e.g. "there is confidential material on this topic you don't have access to," is acceptable).
- Reversal trigger: If a real scenario emerges where Confidential-tier content actually needs full existence-hiding (e.g. an active legal matter initially tagged Confidential), that specific object should be reclassified to Restricted rather than changing this ADR's tier behavior.
- Related ADR/tests: RV-DEC-0005 (classification labels), P4-GATE (permission filter tests), P6-GATE (permission-safe bounded neighborhoods — "traversal stops at unauthorized nodes or edges," Product Build Plan section 18.2), P7-GATE (permission benchmarks), P10 security checklist (IDOR/cross-permission negative tests should include existence-leak checks specifically for Restricted content).
