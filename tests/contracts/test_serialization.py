import json

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.contracts.identifiers import generate_id


def test_normalized_document_serialization():
    doc_id = generate_id("doc")
    ver_id = generate_id("ver")
    blk_id = generate_id("blk")

    doc = NormalizedDocument(
        document_id=doc_id,
        workspace_id="ws_test",
        source_id="src_test",
        title="Test Serialization Document",
        provider=SourceProvider.GOOGLE_DRIVE,
        locator=DocumentLocator(
            provider=SourceProvider.GOOGLE_DRIVE,
            native_id="gdrive_123",
            uri="https://drive.google.com/file/d/gdrive_123",
        ),
        active_version_id=ver_id,
        versions=[
            DocumentVersion(
                version_id=ver_id,
                document_id=doc_id,
                version_number=1,
                content_hash="abc123hash",
                blocks=[
                    DocumentBlock(
                        block_id=blk_id,
                        block_type="heading_1",
                        content="Serialization Heading",
                        sequence=1,
                    )
                ],
            )
        ],
    )

    json_str = doc.model_dump_json()
    data = json.loads(json_str)

    assert data["document_id"] == doc_id
    assert data["provider"] == "google_drive"
    assert data["versions"][0]["blocks"][0]["content"] == "Serialization Heading"

    deserialized = NormalizedDocument.model_validate(data)
    assert deserialized.document_id == doc_id
    assert deserialized.versions[0].blocks[0].block_id == blk_id
