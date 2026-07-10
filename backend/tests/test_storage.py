import pytest

from tests.conftest import InMemoryStorage


@pytest.mark.asyncio
async def test_storage_upload_download_exists_delete() -> None:
    storage = InMemoryStorage()
    path = "client/project/file.pdf"
    data = b"artifact bytes"

    uploaded_path = await storage.upload(path, data, "application/pdf")
    assert uploaded_path == path
    assert await storage.exists(path) is True
    assert await storage.download(path) == data
    assert await storage.delete(path) is True
    assert await storage.exists(path) is False
