import pytest

from rekanvault.contracts.documents import SourceProvider
from rekanvault.sources.notion import NotionConnector


@pytest.mark.asyncio
async def test_notion_connector_scan():
    connector = NotionConnector(source_id="src_notion_1", config={"root_page_id": "page_123"})
    assert connector.provider == SourceProvider.NOTION

    docs = await connector.scan()
    assert len(docs) == 2
    assert docs[0].provider == SourceProvider.NOTION
    assert len(docs[0].versions[0].blocks) == 2


@pytest.mark.asyncio
async def test_notion_connector_reconcile():
    connector = NotionConnector(source_id="src_notion_1", config={})
    res = await connector.reconcile()
    assert res["status"] == "reconciled"
