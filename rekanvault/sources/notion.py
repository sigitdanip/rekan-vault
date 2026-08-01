import hashlib
from datetime import datetime, timezone
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


class NotionConnector(BaseConnector):
    @property
    def provider(self) -> SourceProvider:
        return SourceProvider.NOTION

    async def scan(self) -> list[NormalizedDocument]:
        root_page_id = str(self.config.get("root_page_id", "notion_root_1"))
        mock_pages = [
            {
                "id": "notion_page_1",
                "title": f"Engineering Guidelines ({root_page_id})",
                "blocks": ["Working agreements", "Anti-slop directives"],
            },
            {
                "id": "notion_page_2",
                "title": "ADR Decisions Index",
                "blocks": ["ADR-0001 Private Repo", "ADR-0008 PostgreSQL"],
            },
        ]

        documents: list[NormalizedDocument] = []
        for page_info in mock_pages:
            doc_id = generate_id("doc")
            ver_id = generate_id("ver")
            blocks_list: list[str] = page_info["blocks"]  # type: ignore[assignment]
            content_text = "\n".join(blocks_list)
            content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

            blocks = [
                DocumentBlock(
                    block_id=generate_id("blk"),
                    block_type="bulleted_list_item",
                    content=txt,
                    sequence=idx + 1,
                )
                for idx, txt in enumerate(blocks_list)
            ]

            version = DocumentVersion(
                version_id=ver_id,
                document_id=doc_id,
                version_number=1,
                content_hash=content_hash,
                blocks=blocks,
            )

            page_title = str(page_info["title"])
            page_id = str(page_info["id"])

            doc = NormalizedDocument(
                document_id=doc_id,
                workspace_id=str(self.config.get("workspace_id", "ws_default")),
                source_id=self.source_id,
                title=page_title,
                provider=SourceProvider.NOTION,
                locator=DocumentLocator(
                    provider=SourceProvider.NOTION,
                    native_id=page_id,
                    uri=f"https://notion.so/{page_id}",
                ),
                active_version_id=ver_id,
                versions=[version],
            )
            documents.append(doc)
        return documents

    async def fetch_changes(self, cursor: str | None = None) -> dict[str, Any]:
        return {
            "new_cursor": f"notion_cursor_{datetime.now(timezone.utc).timestamp()}",
            "changes_count": 0,
            "has_more": False,
        }

    async def reconcile(self) -> dict[str, Any]:
        return {"status": "reconciled", "scanned": 2, "reconciled": 2, "errors": 0}
