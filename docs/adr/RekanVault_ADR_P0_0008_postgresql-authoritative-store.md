### RV-DEC-0008 — PostgreSQL is the authoritative control, memory, and graph store, with a pre-committed escalation path for deep traversal

- Phase: P0
- Status: Approved
- Owner: Imi (original recommendation); refined and ratified by Sigit
- Date: 2026-07-31
- Decision required by: P2 (database foundation), re-verified at P6 (graph phase)
- Context: RekanVault needs one authoritative store for identity, source state, normalized documents, typed memory, entity/relation graph, permissions, jobs, and audit records. Candidates include PostgreSQL, a dedicated graph database (e.g. Neo4j), or a document store.

  During P0 review, Sigit indicated that RekanVault's entity/decision/SkillTree relationship chains are expected to run genuinely deep — 6-7 hops — in this specific project (e.g. SkillTree prerequisite chains, multi-step decision-supersession chains, causal chains like "delay event → warehouse → shift manager → staffing policy → exception approval → budget owner"). Public benchmarks consistently show PostgreSQL recursive CTEs degrading significantly at this depth, especially over large datasets, while native graph databases (e.g. Neo4j) handle 6+ hop traversal via index-free adjacency in near-constant time per hop.

  However, RekanVault's pilot corpus is deliberately small (RV-DEC-0002: one bounded Drive tree, one bounded Notion root), which changes the risk profile — CTE degradation is driven by both hop depth AND total graph size, and most published benchmarks assume large datasets (millions of nodes), not RekanVault's pilot scale.

- Options:
  1. PostgreSQL as the single authoritative store for all control-plane, memory, and graph data, with no special handling for deep traversal.
  2. Introduce a dedicated graph database (e.g. Neo4j) now, before P6, specifically to handle the expected 6-7 hop chains.
  3. PostgreSQL as the authoritative store, with (a) explicit bounded/staged traversal depth enforced in the Graph Service and Context Engine, (b) a real benchmark against pilot-scale fixtures once P6 has data, and (c) Apache AGE (a Cypher-query extension that runs inside PostgreSQL, not a separate database) as a pre-committed escalation path if the benchmark shows unacceptable latency.
- Chosen option: Option 3.
- Why:
  - Introducing Neo4j now (Option 2) would violate product principle 15 (self-hostable, vendor-replaceable core) and product principle 13 (indexes/derivatives should be disposable and rebuildable) before there is any real evidence it's needed — RekanVault's actual first-release graph use cases (Product Build Plan section 14: bounded neighborhood expansion, decision timelines, SkillTree prerequisite paths) are the exact workload public sources agree recursive CTEs handle well, even at depth, when the query pattern is "expand and stop" rather than full pathfinding or graph algorithms (PageRank, community detection).
  - The realistic risk is not "the graph is 6-7 hops deep somewhere" — it's "a specific query needs to traverse all 6-7 hops in one pass." Most queries (e.g. "what does this decision affect," "show this entity's neighborhood") stay shallow (1-3 hops) even when the underlying graph is deep. Only specific SkillTree prerequisite-chain or full causal-chain queries would hit the deep end.
  - Doing nothing (Option 1) ignores a real, named risk. Jumping to a new database (Option 2) is premature without measured evidence at RekanVault's actual scale. Option 3 keeps the plan's rebuildability and vendor-independence principles intact while pre-committing to a concrete, low-disruption escalation path (Apache AGE stays inside PostgreSQL — same operational footprint, same backup/rebuild story) if real benchmarks prove the risk is real.
- Impact:
  - P6 (Entity and Temporal Graph) must implement explicit depth bounding in the Graph Service and Context Engine — not "eventually," but as a hard requirement of the bounded-neighborhood API (Product Build Plan section 14.5, section 20.4 already require this; this ADR makes the *reason* for it explicit).
  - P6 must include a benchmark task: run representative 6-7 hop queries (SkillTree prerequisite chains, decision-supersession chains) against pilot-scale fixtures before P6-GATE closes, and record the result.
  - If the benchmark shows unacceptable latency (working threshold: greater than 1-2 seconds for a common 6-7 hop query), the next step is adding Apache AGE as a PostgreSQL extension — not standing up a separate graph database service. This must be evaluated against RV-DEC-0008's principles (rebuildability, vendor independence) before being adopted, but is pre-approved in principle as the first escalation step.
- Reversal trigger: The P6 benchmark shows real, unacceptable latency at pilot scale for genuinely deep (6-7 hop) queries that staged/bounded traversal cannot mitigate. In that case, escalate to Apache AGE first; only escalate to a fully separate graph database (Neo4j or similar) if Apache AGE itself proves insufficient, backed by measured evidence at each step.
- Related ADR/tests: RV-DEC-0002 (pilot corpus scope — informs realistic benchmark scale), P6-GATE (graph fixtures pass under PostgreSQL, including the deep-traversal benchmark), P2-GATE (all authoritative state survives restart), RV-DEC-0013 (hosting topology — PostgreSQL runs on Supabase, not the VPS; see update below).

### Update — 2026-07-31

RV-DEC-0013 (hosting topology) placed PostgreSQL on Supabase rather than on the same VPS as the application code. This adds a network hop between the API/worker processes and the database that did not exist in the original framing of this ADR. **This matters directly for the P6 benchmark commitment above**: a 6-7 hop recursive CTE query now pays network latency on top of query execution time, on every hop if the traversal is staged/sequential rather than a single round-trip query. The P6 benchmark must measure real Supabase-hosted latency, not local-Postgres latency — the "greater than 1-2 seconds" threshold in the Impact section should be re-evaluated once real network conditions are part of the test, since some of that budget will now be consumed by network round trips rather than query execution alone.
