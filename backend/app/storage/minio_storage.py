import asyncio
import io
import logging

from minio import Minio
from minio.error import S3Error

from app.core.config import Settings, get_settings
from app.storage.storage_interface import StorageInterface

logger = logging.getLogger(__name__)


class MinioStorage(StorageInterface):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = Minio(
            self._settings.minio_endpoint,
            access_key=self._settings.minio_access_key,
            secret_key=self._settings.minio_secret_key,
            secure=self._settings.minio_secure,
        )
        self._bucket = self._settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except Exception as exc:
            logger.warning("Failed to ensure MinIO bucket %s: %s", self._bucket, exc)

    async def upload(self, path: str, data: bytes, content_type: str | None = None) -> str:
        return await asyncio.to_thread(self._upload_sync, path, data, content_type)

    def _upload_sync(self, path: str, data: bytes, content_type: str | None) -> str:
        self._ensure_bucket()
        self._client.put_object(
            self._bucket,
            path,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )
        return path

    async def download(self, path: str) -> bytes:
        return await asyncio.to_thread(self._download_sync, path)

    def _download_sync(self, path: str) -> bytes:
        response = self._client.get_object(self._bucket, path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, path: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, path)

    def _delete_sync(self, path: str) -> bool:
        try:
            self._client.remove_object(self._bucket, path)
            return True
        except S3Error as exc:
            logger.warning("Failed to delete object %s: %s", path, exc)
            return False

    async def exists(self, path: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, path)

    def _exists_sync(self, path: str) -> bool:
        try:
            self._client.stat_object(self._bucket, path)
            return True
        except S3Error:
            return False
