"""Citation resolver for evidence chunks.

Builds :class:`Citation` objects from chunk metadata. URI format is
per-source: Google Drive uses the file-view URL, Notion uses the page
URL with the external (block) UUID preserved per P3-T8.
"""

from __future__ import annotations

from typing import Any

from rekanvault.contracts.evidence import Citation

_SNIPPET_LIMIT = 200

# Source-type → URI template. ``{external_id}`` is substituted.
# ponytail: if a third source type appears, add the template here; the
# resolver does not pretend to know more than the table.
_URI_TEMPLATES: dict[str, str] = {
    "google_drive": "https://drive.google.com/file/d/{external_id}/view",
    "notion": "https://notion.so/{external_id}",
}


class CitationResolver:
    """Build :class:`Citation` objects from chunk metadata.

    The resolver is stateless and cheap — instantiate once and reuse.
    """

    def resolve(
        self,
        chunk_metadata: dict[str, Any],
        *,
        document_id: str,
        version_id: str,
        content: str = "",
    ) -> Citation:
        """Resolve a citation from chunk metadata + required fields.

        Required inputs (passed positionally/keyword because metadata
        alone does not always carry them):
          - ``document_id``: owning document
          - ``version_id``: document version
          - ``content``: raw chunk content (for snippet)

        The ``chunk_metadata`` dict typically carries: ``title``,
        ``source_type`` (e.g. ``"google_drive"``), ``external_id``,
        ``block_id`` (Notion block UUIDs preserved per P3-T8), and any
        chunker-specific keys.
        """
        title = str(chunk_metadata.get("title", ""))
        external_id = str(chunk_metadata.get("external_id", ""))
        source_type = str(chunk_metadata.get("source_type", ""))
        block_id = chunk_metadata.get("block_id")
        snippet = content[:_SNIPPET_LIMIT]

        return Citation(
            document_id=document_id,
            version_id=version_id,
            block_id=str(block_id) if block_id is not None else None,
            title=title,
            uri=self._build_uri(source_type, external_id),
            snippet=snippet,
        )

    @staticmethod
    def _build_uri(source_type: str, external_id: str) -> str:
        template = _URI_TEMPLATES.get(source_type)
        if template is None:
            # ponytail: unknown source — return a generic uri rather than
            # raising. The citation stays usable; consumers can tell
            # from the host that it is a placeholder.
            return f"https://example.invalid/{external_id}" if external_id else ""
        return template.format(external_id=external_id)
