import pytest

from rekanvault.contracts.documents import SourceProvider
from rekanvault.sources.google_drive import GoogleDriveConnector


@pytest.mark.asyncio
async def test_gdrive_connector_scan():
    connector = GoogleDriveConnector(source_id="src_gdrive_1", config={"folder_id": "folder_abc"})
    assert connector.provider == SourceProvider.GOOGLE_DRIVE

    docs = await connector.scan()
    assert len(docs) == 2
    assert docs[0].provider == SourceProvider.GOOGLE_DRIVE
    assert len(docs[0].versions) == 1
    assert len(docs[0].versions[0].blocks) == 1


@pytest.mark.asyncio
async def test_gdrive_connector_reconcile():
    connector = GoogleDriveConnector(source_id="src_gdrive_1", config={})
    res = await connector.reconcile()
    assert res["status"] == "reconciled"
    assert res["scanned"] == 2
