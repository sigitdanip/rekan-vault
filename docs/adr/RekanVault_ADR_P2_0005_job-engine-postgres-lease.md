### RV-DEC-P2-0005 — Architecture: PostgreSQL-backed durable job queue (FOR UPDATE SKIP LOCKED) without Redis

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 durable job engine implementation
- Context: SDLC Phase 2 establishes background job processing (sync, extraction, outbox events). The system requires durable job claiming, retries, heartbeat, and dead-letter state.
- Options:
  1. Custom PostgreSQL lease table using `FOR UPDATE SKIP LOCKED` and advisory locks (no Redis dependency).
  2. Introduce Redis (Celery / BullMQ) as a dedicated background job broker.
- Chosen option: Option 1 — Custom PostgreSQL lease table (`processing_jobs`) in PostgreSQL.
- Why: Keeps the deployment topology simple and resource-light on the VPS without introducing a mandatory Redis service dependency (RV-DEC-0007, RV-DEC-0013). PostgreSQL is already transactional, authoritative, and hosted on Supabase with automatic backup/failover.
- Impact: Job claims, worker leases, retries, and outbox transactions commit atomically in PostgreSQL. Removes mandatory `RV_REDIS_URL` dependency during initial phases.
- Escalation path & Reversal trigger: Redis (Celery / BullMQ) is **pre-approved as the explicit escalation path** if P10 resource profiling, soak testing, or real high-frequency job queue throughput proves PostgreSQL lock contention or connection pool exhaustion to be a bottleneck.
- Related ADR/tests: RV-DEC-0007 (modular monolith plus workers), RV-DEC-0008 (PostgreSQL authoritative store), RV-DEC-0013 (hosting topology), P10 resource profiling.
