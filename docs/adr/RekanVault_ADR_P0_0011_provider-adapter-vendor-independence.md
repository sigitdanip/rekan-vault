### RV-DEC-0011 — Extractors, embeddings, rerankers, vector stores, and language models stay behind replaceable provider-adapter interfaces

- Phase: P0
- Status: Approved
- Owner: Imi; ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P3 (source extraction), P4 (embeddings/reranking), P5/P7 (LLM provider)
- Context: RekanVault depends on several external or swappable components: document extractors, embedding models, rerankers, vector stores (Qdrant), and language models (currently planned as Groq via an OpenAI-compatible endpoint). Coupling code directly to any one vendor's SDK/API shape makes future substitution expensive and risky.
- Options:
  1. Call each provider's SDK directly wherever needed in the codebase.
  2. Define a stable internal interface per capability (extraction, embedding, reranking, vector store, LLM completion), with one adapter implementation per provider behind it.
- Chosen option: Option 2.
- Why: Product principle 14 requires model and vendor independence. Concretely, this means the LLM provider (Groq-compatible today) can be swapped without touching memory-formation or answer-generation logic, and the embedding/reranking models (BGE-M3 / BGE-reranker-v2-m3 candidates) can be re-evaluated or replaced as better multilingual options emerge, without a rewrite.
- Impact: `rekanvault/` internal modules depend only on the adapter interfaces, never directly on `openai`, `qdrant-client`, or `sentence-transformers` APIs outside the adapter implementation itself. Model identity (provider, model ID, revision, dimensions) is recorded in `component_versions` per SDLC plan section 3.4, not hardcoded.
- Reversal trigger: None anticipated as a reversal — this is a structural discipline maintained throughout the project, re-affirmed whenever a new provider type is introduced.
- Related ADR/tests: RV-DEC-0009 (Qdrant rebuildability — same vendor-independence principle applied to the vector store specifically), P4/P5/P7 exit gates (model swap should not require logic changes, only adapter/config changes).
