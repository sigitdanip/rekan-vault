from rekanvault.contracts.documents import (
    DocumentLocator,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.contracts.events import EventType
from rekanvault.ingestion.lifecycle import IngestionLifecycleManager
from rekanvault.ingestion.reconciliation import ReconciliationEngine


def test_ingestion_lifecycle_events():
    mgr = IngestionLifecycleManager()
    doc = NormalizedDocument(
        document_id="doc_test_100",
        workspace_id="ws_default",
        source_id="src_1",
        title="Doc Title",
        provider=SourceProvider.GOOGLE_DRIVE,
        locator=DocumentLocator(provider=SourceProvider.GOOGLE_DRIVE, native_id="1", uri="http://example.com"),
        active_version_id="ver_100",
        versions=[],
    )

    events1 = mgr.process_document(doc)
    assert len(events1) == 1
    assert events1[0].event_type == EventType.DOCUMENT_CREATED

    events2 = mgr.process_document(doc)
    assert len(events2) == 1
    assert events2[0].event_type == EventType.DOCUMENT_UPDATED


def test_reconciliation_engine():
    engine = ReconciliationEngine()
    doc1 = NormalizedDocument(
        document_id="doc_1",
        workspace_id="ws_1",
        source_id="src_1",
        title="A",
        provider=SourceProvider.NOTION,
        locator=DocumentLocator(provider=SourceProvider.NOTION, native_id="1", uri="uri"),
        active_version_id="v1",
    )
    doc2 = NormalizedDocument(
        document_id="doc_2",
        workspace_id="ws_1",
        source_id="src_1",
        title="B",
        provider=SourceProvider.NOTION,
        locator=DocumentLocator(provider=SourceProvider.NOTION, native_id="2", uri="uri"),
        active_version_id="v2",
    )

    res = engine.reconcile(expected=[doc1], actual=[doc1, doc2])
    assert res["reconciled"] == ["doc_1"]
    assert res["new"] == ["doc_2"]
    assert res["missing"] == []
