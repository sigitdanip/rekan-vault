### RV-DEC-P2-0005 — Architecture: Introduce Redis as dedicated job broker for Phase 2

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 durable job engine implementation
- Context: SDLC Phase 2 establishes background job processing (sync, extraction, outbox events). Initial plan proposed custom PostgreSQL lease tables (`FOR UPDATE SKIP LOCKED`).
- Options:
  1. Custom PostgreSQL lease table initially, avoiding Redis.
  2. Introduce Redis (Celery / BullMQ) as a dedicated background job broker from Phase 2.
- Chosen option: Option 2 — Introduce Redis as dedicated job broker, updating initial hosting topology assumptions.
- Why: Provides high-throughput job queuing, native rate limiting, delayed execution, and eliminates database locking overhead on high-frequency worker tasks.
- Impact: Redis service added to VPS topology (`RV_REDIS_URL`). Worker process (`apps/worker`) connects to Redis for queue management while PostgreSQL maintains durable job attempt/history state.
- Reversal trigger: VPS memory pressure exceeding allocation limits under light load.
- Related ADR/tests: RV-DEC-0007 (modular monolith plus workers), RV-DEC-0013 (hosting topology).
