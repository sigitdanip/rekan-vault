import hashlib
from datetime import UTC, datetime
from typing import Any

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.contracts.identifiers import generate_id
from rekanvault.sources.base import BaseConnector


class GoogleDriveConnector(BaseConnector):
    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.GOOGLE_DRIVE

    async def scan(self) -> list[NormalizedDocument]:
        folder_id = self.config.get("folder_id", "root")
        mock_files = [
            {
                "id": "gdrive_file_1",
                "name": "Architecture Overview.gdoc",
                "mime": "application/vnd.google-apps.document",
                "content": f"RekanVault Architecture Overview for folder {folder_id}.",
            },
            {
                "id": "gdrive_file_2",
                "name": "Q3 Roadmap.gdoc",
                "mime": "application/vnd.google-apps.document",
                "content": "Phase 1 Monorepo, Phase 2 PostgreSQL, Phase 3 Connectors.",
            },
        ]

        documents: list[NormalizedDocument] = []
        for file_info in mock_files:
            doc_id = generate_id("doc")
            ver_id = generate_id("ver")
            blk_id = generate_id("blk")
            content_hash = hashlib.sha256(file_info["content"].encode("utf-8")).hexdigest()

            version = DocumentVersion(
                version_id=ver_id,
                document_id=doc_id,
                version_number=1,
                content_hash=content_hash,
                blocks=[
                    DocumentBlock(
                        block_id=blk_id,
                        block_type="paragraph",
                        content=file_info["content"],
                        sequence=1,
                    )
                ],
            )

            doc = NormalizedDocument(
                document_id=doc_id,
                workspace_id=self.config.get("workspace_id", "ws_default"),
                source_id=self.source_id,
                title=file_info["name"],
                provider=SourceProvider.GOOGLE_DRIVE,
                locator=DocumentLocator(
                    provider=SourceProvider.GOOGLE_DRIVE,
                    native_id=file_info["id"],
                    uri=f"https://drive.google.com/file/d/{file_info['id']}",
                    mime_type=file_info["mime"],
                ),
                active_version_id=ver_id,
                versions=[version],
            )
            documents.append(doc)
        return documents

    async def fetch_changes(self, cursor: str | None = None) -> dict[str, Any]:
        return {
            "new_cursor": f"cursor_{datetime.now(UTC).timestamp()}",
            "changes_count": 0,
            "has_more": False,
        }

    async def reconcile(self) -> dict[str, Any]:
        return {"status": "reconciled", "scanned": 2, "reconciled": 2, "errors": 0}
