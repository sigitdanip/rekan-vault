### RV-DEC-P5-0002 — LLM Provider Abstraction and Immutable Prompt Registry

- Phase: P5
- Status: Approved
- Owner: Sigit
- Date: 2026-08-12
- Decision required by: Phase P5 LLM extraction and structured output engine
- Context: Typed memory extraction requires calling external LLM providers (e.g. Groq / OpenAI compatible API) to process document chunks into structured memory JSON, while guarding against vendor lock-in, prompt injection (Risk R-004), and unversioned prompt changes.
- Options:
  1. Wrap LLM calls behind a RekanVault provider interface using the `openai` SDK (`RV_LLM_PROVIDER`, `RV_LLM_BASE_URL`, `RV_LLM_API_KEY`, `RV_EXTRACTION_MODEL`) with native Python orchestration. Maintain an immutable versioned prompt registry in code. Enforce structural prompt boundaries where source content is strictly passed as data.
  2. Heavy RAG/extraction frameworks like LangChain or LlamaIndex with implicit prompt templates.
- Chosen option: Option 1 — RekanVault OpenAI-compatible provider wrapper + immutable prompt registry + explicit prompt injection boundary.
- Why: Keeps zero framework bloat, guarantees vendor independence (compatible with Groq, OpenAI, Ollama, vLLM), ensures prompt version traceability in telemetry/audit logs, and mitigates prompt injection risks.
- Impact: `rekanvault/memory/llm.py` provider wrapper and `rekanvault/memory/prompts.py` registry created.
- Reversal trigger: If provider API standard diverges or structured JSON mode requires provider-specific SDK features.
- Related ADR/tests: P5-T3 (prompt injection boundary), P5-T9 (provider timeout/rate-limit error handling), Risk R-004.
