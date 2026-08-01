# RekanVault

RekanVault is a personal knowledge base and RAG engine that turns messy personal documents and notes into verified knowledge, active memory, and grounded answers.

## Monorepo Architecture

- `rekanvault/`: Python domain contracts, connectors, ingestion, retrieval, memory, graph, context, skills, governance, and storage adapters.
- `apps/api/`: FastAPI entrypoint and HTTP composition.
- `apps/worker/`: Sync, extraction, indexing, memory, and maintenance worker process.
- `apps/web/`: Next.js Web Shell interface.
- `packages/contracts/`: Versioned OpenAPI 3.1 and JSON Schemas.
- `docs/`: Product Build Plan, SDLC Plan, ADRs, risk register, workflows, and matrix.
- `tests/`: Categorized test suite.

## Development

```bash
# Set up Python environment
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Set up Web environment
pnpm install
```
