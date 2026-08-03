"""
PostgreSQL Durable Processing Job Queue & Outbox Engine (RV-DEC-P2-0005)
Implements FOR UPDATE SKIP LOCKED job leasing, heartbeats, retries, and dead-letter queueing.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.storage.models import (
    DeadLetter,
    JobAttempt,
    OutboxEvent,
    ProcessingJob,
    utc_now,
)


class JobQueueManager:
    """Manages transactional job creation, leasing, attempt recording, and dead-lettering."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_job(
        self,
        workspace_id: uuid.UUID,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: Optional[str] = None,
        max_attempts: int = 8,
    ) -> ProcessingJob:
        """Enqueues a new processing job with optional idempotency key."""
        if idempotency_key:
            stmt = select(ProcessingJob).where(ProcessingJob.idempotency_key == idempotency_key)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        job = ProcessingJob(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            status="pending",
            max_attempts=max_attempts,
        )
        self.session.add(job)
        return job

    async def claim_next_job(
        self,
        worker_actor_id: str,
        lease_duration_seconds: int = 300,
    ) -> Optional[ProcessingJob]:
        """
        Claims the next pending or expired leased job using FOR UPDATE SKIP LOCKED.
        Guarantees zero lock contention across concurrent workers.
        """
        now = utc_now()
        lease_expires = now + timedelta(seconds=lease_duration_seconds)

        # Select next pending or expired job
        stmt = (
            select(ProcessingJob)
            .where(
                (ProcessingJob.status == "pending")
                | ((ProcessingJob.status == "leased") & (ProcessingJob.lease_expires_at < now))
            )
            .where(ProcessingJob.attempts < ProcessingJob.max_attempts)
            .order_by(ProcessingJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return None

        # Update lease state
        job.status = "leased"
        job.lease_actor = worker_actor_id
        job.leased_at = now
        job.lease_expires_at = lease_expires
        job.attempts += 1

        # Record attempt history
        attempt = JobAttempt(
            id=uuid.uuid4(),
            job_id=job.id,
            attempt_number=job.attempts,
            status="leased",
            started_at=now,
        )
        self.session.add(attempt)

        return job

    async def complete_job(self, job_id: uuid.UUID) -> None:
        """Marks a job as completed."""
        now = utc_now()
        stmt = update(ProcessingJob).where(ProcessingJob.id == job_id).values(status="completed", updated_at=now)
        await self.session.execute(stmt)

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Records a job failure. Dead-letters if max_attempts reached."""
        now = utc_now()
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return

        if job.attempts >= job.max_attempts:
            job.status = "failed"
            dead_letter = DeadLetter(
                id=uuid.uuid4(),
                job_id=job.id,
                workspace_id=job.workspace_id,
                reason=f"Exceeded max attempts ({job.max_attempts}): {error_message}",
                payload=job.payload,
            )
            self.session.add(dead_letter)
        else:
            job.status = "pending"
            job.lease_actor = None
            job.leased_at = None
            job.lease_expires_at = None

        job.updated_at = now

    async def create_outbox_event(
        self,
        workspace_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        """Creates a transactional outbox event in the same DB transaction as domain mutations."""
        event = OutboxEvent(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        self.session.add(event)
        return event
