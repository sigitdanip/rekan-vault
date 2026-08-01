import uuid
from typing import Annotated

from pydantic import Field


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


WorkspaceId = Annotated[str, Field(pattern=r"^ws_[a-f0-9]{16}$", description="Workspace identifier")]
SourceId = Annotated[str, Field(pattern=r"^src_[a-f0-9]{16}$", description="Source connector identifier")]
DocumentId = Annotated[str, Field(pattern=r"^doc_[a-f0-9]{16}$", description="Normalized document identifier")]
VersionId = Annotated[str, Field(pattern=r"^ver_[a-f0-9]{16}$", description="Document version identifier")]
MemoryId = Annotated[str, Field(pattern=r"^mem_[a-f0-9]{16}$", description="Memory record identifier")]
EntityId = Annotated[str, Field(pattern=r"^ent_[a-f0-9]{16}$", description="Graph entity identifier")]
RelationId = Annotated[str, Field(pattern=r"^rel_[a-f0-9]{16}$", description="Graph relation identifier")]
ContextPackId = Annotated[str, Field(pattern=r"^ctx_[a-f0-9]{16}$", description="Context pack identifier")]
SkillId = Annotated[str, Field(pattern=r"^skl_[a-f0-9]{16}$", description="Skill tree node identifier")]
AuditId = Annotated[str, Field(pattern=r"^aud_[a-f0-9]{16}$", description="Audit log entry identifier")]
