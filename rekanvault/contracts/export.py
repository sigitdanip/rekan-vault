import json
from pathlib import Path

from pydantic import BaseModel

from rekanvault.contracts.audit import AuditLogEntry
from rekanvault.contracts.context import ContextPack, GroundedAnswer
from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentVersion,
    ExtractionWarning,
    NormalizedDocument,
)
from rekanvault.contracts.errors import ErrorEnvelope
from rekanvault.contracts.events import LifecycleEvent
from rekanvault.contracts.evidence import Citation, EvidenceChunk, RerankedEvidence
from rekanvault.contracts.graph import EntityRecord, RelationRecord
from rekanvault.contracts.memory import MemoryRecord
from rekanvault.contracts.skills import SkillNode, SkillProgress
from rekanvault.contracts.sources import (
    JobTriggerResponse,
    RegisterSourceRequest,
    SourceDetail,
    SourceHealth,
    SourceSummary,
)

EXPORT_MODELS: dict[str, type[BaseModel]] = {
    "NormalizedDocument": NormalizedDocument,
    "DocumentVersion": DocumentVersion,
    "DocumentBlock": DocumentBlock,
    "ExtractionWarning": ExtractionWarning,
    "ErrorEnvelope": ErrorEnvelope,
    "LifecycleEvent": LifecycleEvent,
    "EvidenceChunk": EvidenceChunk,
    "Citation": Citation,
    "RerankedEvidence": RerankedEvidence,
    "MemoryRecord": MemoryRecord,
    "EntityRecord": EntityRecord,
    "RelationRecord": RelationRecord,
    "ContextPack": ContextPack,
    "GroundedAnswer": GroundedAnswer,
    "SkillNode": SkillNode,
    "SkillProgress": SkillProgress,
    "AuditLogEntry": AuditLogEntry,
    "RegisterSourceRequest": RegisterSourceRequest,
    "SourceSummary": SourceSummary,
    "SourceDetail": SourceDetail,
    "SourceHealth": SourceHealth,
    "JobTriggerResponse": JobTriggerResponse,
}


def export_all_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, model_cls in EXPORT_MODELS.items():
        schema = model_cls.model_json_schema()
        target_file = output_dir / f"{name}.schema.json"
        target_file.write_text(json.dumps(schema, indent=2))
    print(f"Exported {len(EXPORT_MODELS)} JSON schemas to {output_dir}")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    schema_dir = repo_root / "packages" / "contracts" / "schemas"
    export_all_schemas(schema_dir)
