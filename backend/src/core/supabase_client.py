"""Supabase client initialization and storage helpers."""

import os
import tempfile
from contextlib import contextmanager
from typing import Optional

import structlog
from supabase import Client, create_client

from src.core.config import settings

logger = structlog.get_logger(__name__)

_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Get or create the Supabase client singleton."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "supabase_not_configured",
            msg="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set",
        )
        return None

    try:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        logger.info("supabase_client_initialized", url=settings.SUPABASE_URL)
        return _supabase_client
    except Exception as exc:
        logger.error("supabase_client_init_failed", error=str(exc))
        return None


def is_storage_key(path: str) -> bool:
    """Check if a path is a Supabase Storage key (not a local filesystem path).

    Returns True when path doesn't start with '/' or './' — i.e. it looks like
    a relative storage key such as 'documents/org123/doc456/file.pdf'.
    """
    if not path:
        return False
    return not path.startswith("/") and not path.startswith("./")


def parse_storage_key(path: str) -> tuple[str, str]:
    """Parse a storage key into (bucket, key).

    Storage keys use the format: '{bucket}/{rest_of_key}'.
    Example: 'documents/org123/doc456/file.pdf' -> ('documents', 'org123/doc456/file.pdf')
    """
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid storage key format: {path}")
    return parts[0], parts[1]


class StorageHelper:
    """Helper class for Supabase Storage operations."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
        if self.client is None:
            raise RuntimeError(
                "Supabase client not available. "
                "Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        self._log = logger.bind(component="storage_helper")

    def upload_file(
        self,
        bucket: str,
        key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to Supabase Storage.

        Returns the storage key '{bucket}/{key}'.
        """
        self._log.info(
            "storage_upload_start",
            bucket=bucket,
            key=key,
            content_type=content_type,
            size_bytes=len(file_data),
        )
        try:
            self.client.storage.from_(bucket).upload(
                path=key,
                file=file_data,
                file_options={"content-type": content_type},
            )
            storage_key = f"{bucket}/{key}"
            self._log.info("storage_upload_complete", storage_key=storage_key)
            return storage_key
        except Exception as exc:
            self._log.error(
                "storage_upload_failed", bucket=bucket, key=key, error=str(exc)
            )
            raise

    def download_file(self, bucket: str, key: str) -> bytes:
        """Download a file from Supabase Storage. Returns file bytes."""
        self._log.debug("storage_download_start", bucket=bucket, key=key)
        try:
            data = self.client.storage.from_(bucket).download(key)
            self._log.debug(
                "storage_download_complete", bucket=bucket, key=key, size_bytes=len(data)
            )
            return data
        except Exception as exc:
            self._log.error(
                "storage_download_failed", bucket=bucket, key=key, error=str(exc)
            )
            raise

    def delete_file(self, bucket: str, key: str) -> bool:
        """Delete a file from Supabase Storage. Returns True on success."""
        self._log.info("storage_delete_start", bucket=bucket, key=key)
        try:
            self.client.storage.from_(bucket).remove([key])
            self._log.info("storage_delete_complete", bucket=bucket, key=key)
            return True
        except Exception as exc:
            self._log.error(
                "storage_delete_failed", bucket=bucket, key=key, error=str(exc)
            )
            return False

    def create_signed_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        """Create a signed URL for temporary file access.

        Args:
            bucket: Storage bucket name.
            key: Object key within the bucket.
            expires_in: URL validity in seconds (default 1 hour).

        Returns:
            Signed URL string.
        """
        self._log.debug(
            "storage_signed_url_start",
            bucket=bucket,
            key=key,
            expires_in=expires_in,
        )
        try:
            result = self.client.storage.from_(bucket).create_signed_url(
                key, expires_in
            )
            url = result.get("signedURL") or result.get("signedUrl", "")
            self._log.debug("storage_signed_url_complete", bucket=bucket, key=key)
            return url
        except Exception as exc:
            self._log.error(
                "storage_signed_url_failed",
                bucket=bucket,
                key=key,
                error=str(exc),
            )
            raise

    def download_to_tempfile(self, bucket: str, key: str, suffix: str = "") -> str:
        """Download a file from Storage to a temporary file on disk.

        The caller is responsible for cleaning up the temp file.

        Args:
            bucket: Storage bucket name.
            key: Object key within the bucket.
            suffix: Optional file extension suffix (e.g. '.pdf').

        Returns:
            Absolute path to the temporary file.
        """
        temp_dir = getattr(settings, "SUPABASE_STORAGE_TEMP_DIR", "/tmp/rag_storage")
        os.makedirs(temp_dir, exist_ok=True)

        data = self.download_file(bucket, key)

        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=temp_dir)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

        self._log.info(
            "storage_download_to_tempfile",
            bucket=bucket,
            key=key,
            temp_path=temp_path,
            size_bytes=len(data),
        )
        return temp_path

    def check_health(self) -> bool:
        """Check if Supabase Storage is reachable."""
        try:
            self.client.storage.list_buckets()
            return True
        except Exception as exc:
            self._log.error("storage_health_check_failed", error=str(exc))
            return False
