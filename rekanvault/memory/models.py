"""Pydantic v2 domain schemas for Phase 5 Typed Memory Formation and Review.

Implements all 18 typed memory schemas per RV-DEC-P5-0001 & P5-T1:
Fact, Claim, Decision, Policy, Procedure, Event, Project, Task, Idea,
Risk, Assumption, Lesson, Metric, Person, Organization, Topic, Asset, Skill.

Configured with strict `extra="forbid"` (P5-T2) to reject hallucinated or
unknown fields from LLM extraction outputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    FACT = "Fact"
    CLAIM = "Claim"
    DECISION = "Decision"
    POLICY = "Policy"
    PROCEDURE = "Procedure"
    EVENT = "Event"
    PROJECT = "Project"
    TASK = "Task"
    IDEA = "Idea"
    RISK = "Risk"
    ASSUMPTION = "Assumption"
    LESSON = "Lesson"
    METRIC = "Metric"
    PERSON = "Person"
    ORGANIZATION = "Organization"
    TOPIC = "Topic"
    ASSET = "Asset"
    SKILL = "Skill"


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    UNSUPPORTED = "unsupported"


# High-impact categories that MUST enter human review queue (RV-DEC-P5-0001, P5-T7)
HIGH_IMPACT_MEMORY_TYPES: set[MemoryType] = {
    MemoryType.DECISION,
    MemoryType.POLICY,
    MemoryType.RISK,
}


class BaseTypedMemory(BaseModel):
    """Base schema for all 18 typed memory records."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    memory_type: MemoryType
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = Field(..., min_length=1)
    impact: ImpactLevel = ImpactLevel.MEDIUM
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    created_by_user_id: UUID | None = None
    prompt_version: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FactMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.FACT] = MemoryType.FACT
    statement: str
    verification_method: str | None = None


class ClaimMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.CLAIM] = MemoryType.CLAIM
    assertion: str
    supports_count: int = 0
    contradicts_count: int = 0


class DecisionMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.DECISION] = MemoryType.DECISION
    rationale: str = ""  # ponytail: optional — LLM omits it on misclassification (5/7 failures)
    alternatives_considered: list[str] = Field(default_factory=list)
    decision_maker: str | None = None
    status: str = "active"  # active, superseded, reversed


class PolicyMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.POLICY] = MemoryType.POLICY
    directive: str
    enforcement_scope: str | None = None
    mandatory: bool = True


class ProcedureMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.PROCEDURE] = MemoryType.PROCEDURE
    steps: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class EventMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.EVENT] = MemoryType.EVENT
    occurred_at: datetime | None = None
    location: str | None = None
    participants: list[str] = Field(default_factory=list)


class ProjectMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.PROJECT] = MemoryType.PROJECT
    project_code: str | None = None
    status: str = "active"  # planning, active, completed, archived
    owner: str | None = None


class TaskMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.TASK] = MemoryType.TASK
    assignee: str | None = None
    due_date: datetime | None = None
    task_status: str = "open"  # open, in_progress, completed, blocked


class IdeaMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.IDEA] = MemoryType.IDEA
    proposal: str
    potential_impact: str | None = None


class RiskMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.RISK] = MemoryType.RISK
    threat: str
    mitigation: str | None = None
    severity: str = "MEDIUM"


class AssumptionMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.ASSUMPTION] = MemoryType.ASSUMPTION
    premise: str
    validation_status: str = "unverified"  # unverified, validated, invalidated


class LessonMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.LESSON] = MemoryType.LESSON
    takeaway: str
    context_description: str | None = None


class MetricMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.METRIC] = MemoryType.METRIC
    metric_name: str
    metric_value: float | str
    unit: str | None = None
    target_value: float | str | None = None


class PersonMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.PERSON] = MemoryType.PERSON
    name: str
    role: str | None = None
    organization: str | None = None


class OrganizationMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.ORGANIZATION] = MemoryType.ORGANIZATION
    organization_name: str
    industry: str | None = None


class TopicMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.TOPIC] = MemoryType.TOPIC
    topic_name: str
    description: str | None = None


class AssetMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.ASSET] = MemoryType.ASSET
    asset_name: str
    asset_type: str | None = None


class SkillMemory(BaseTypedMemory):
    memory_type: Literal[MemoryType.SKILL] = MemoryType.SKILL
    skill_name: str
    proficiency_level: str | None = None


# Mapping of MemoryType to its specific Pydantic model class
TYPED_MEMORY_MODELS: dict[MemoryType, type[BaseTypedMemory]] = {
    MemoryType.FACT: FactMemory,
    MemoryType.CLAIM: ClaimMemory,
    MemoryType.DECISION: DecisionMemory,
    MemoryType.POLICY: PolicyMemory,
    MemoryType.PROCEDURE: ProcedureMemory,
    MemoryType.EVENT: EventMemory,
    MemoryType.PROJECT: ProjectMemory,
    MemoryType.TASK: TaskMemory,
    MemoryType.IDEA: IdeaMemory,
    MemoryType.RISK: RiskMemory,
    MemoryType.ASSUMPTION: AssumptionMemory,
    MemoryType.LESSON: LessonMemory,
    MemoryType.METRIC: MetricMemory,
    MemoryType.PERSON: PersonMemory,
    MemoryType.ORGANIZATION: OrganizationMemory,
    MemoryType.TOPIC: TopicMemory,
    MemoryType.ASSET: AssetMemory,
    MemoryType.SKILL: SkillMemory,
}


def determine_review_status(
    memory_type: MemoryType,
    impact: ImpactLevel,
    confidence: float,
    confidence_threshold: float = 0.85,
) -> ReviewStatus:
    """Determine review status per RV-DEC-P5-0001 & P5-T7.

    High-impact types (Decision, Policy, Risk), high impact levels (HIGH, CRITICAL),
    or low confidence (< threshold) MUST route to pending_review.
    Low-impact entity mentions with high confidence auto-commit to approved.
    """
    if memory_type in HIGH_IMPACT_MEMORY_TYPES:
        return ReviewStatus.PENDING_REVIEW
    if impact in (ImpactLevel.HIGH, ImpactLevel.CRITICAL):
        return ReviewStatus.PENDING_REVIEW
    if confidence < confidence_threshold:
        return ReviewStatus.PENDING_REVIEW
    return ReviewStatus.APPROVED
