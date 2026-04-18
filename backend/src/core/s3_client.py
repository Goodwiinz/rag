"""S3-compatible object storage client for DigitalOcean Spaces."""

import os
import tempfile
from typing import Optional

import structlog

from src.core.config import settings

logger = structlog.get_logger(__name__)

_s3_client = None


def get_s3_client():
    """Get or create the boto3 S3 client singleton."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    if not settings.S3_ENDPOINT_URL or not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
        logger.warning(
            "s3_not_configured",
            msg="S3_ENDPOINT_URL, S3_ACCESS_KEY, or S3_SECRET_KEY not set",
        )
        return None

    try:
        import boto3
        from botocore.config import Config

        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=30,
            ),
        )
        logger.info(
            "s3_client_initialized",
            endpoint=settings.S3_ENDPOINT_URL,
            bucket=settings.S3_BUCKET_NAME,
        )
        return _s3_client
    except Exception as exc:
        logger.error("s3_client_init_failed", error=str(exc))
        return None


class S3StorageHelper:
    """Helper class for S3-compatible storage operations (DigitalOcean Spaces)."""

    def __init__(self, client=None):
        self.client = client or get_s3_client()
        if self.client is None:
            raise RuntimeError(
                "S3 client not available. "
                "Check S3_ENDPOINT_URL, S3_ACCESS_KEY, and S3_SECRET_KEY."
            )
        self.bucket = settings.S3_BUCKET_NAME
        self._log = logger.bind(component="s3_storage_helper")

    def upload_file(
        self,
        key: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to S3/Spaces. Returns the object key."""
        self._log.info(
            "s3_upload_start",
            key=key,
            content_type=content_type,
            size_bytes=len(file_data),
        )
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_data,
                ContentType=content_type,
                ACL="private",
            )
            self._log.info("s3_upload_complete", key=key)
            return key
        except Exception as exc:
            self._log.error("s3_upload_failed", key=key, error=str(exc))
            raise

    def download_file(self, key: str) -> bytes:
        """Download a file from S3/Spaces. Returns file bytes."""
        self._log.debug("s3_download_start", key=key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            data = response["Body"].read()
            self._log.debug("s3_download_complete", key=key, size_bytes=len(data))
            return data
        except Exception as exc:
            self._log.error("s3_download_failed", key=key, error=str(exc))
            raise

    def delete_file(self, key: str) -> bool:
        """Delete a file from S3/Spaces. Returns True on success."""
        self._log.info("s3_delete_start", key=key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            self._log.info("s3_delete_complete", key=key)
            return True
        except Exception as exc:
            self._log.error("s3_delete_failed", key=key, error=str(exc))
            return False

    def create_signed_url(self, key: str, expires_in: int = 900) -> str:
        """Create a presigned URL for temporary file access.

        Args:
            key: Object key within the bucket.
            expires_in: URL validity in seconds (default 15 minutes).

        Returns:
            Presigned URL string.
        """
        self._log.debug("s3_signed_url_start", key=key, expires_in=expires_in)
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            self._log.debug("s3_signed_url_complete", key=key)
            return url
        except Exception as exc:
            self._log.error("s3_signed_url_failed", key=key, error=str(exc))
            raise

    def get_cdn_url(self, key: str) -> Optional[str]:
        """Get CDN URL for a file if CDN endpoint is configured."""
        if settings.S3_CDN_ENDPOINT:
            return f"{settings.S3_CDN_ENDPOINT.rstrip('/')}/{key}"
        return None

    def download_to_tempfile(self, key: str, suffix: str = "") -> str:
        """Download a file from S3/Spaces to a temporary file on disk.

        The caller is responsible for cleaning up the temp file.

        Args:
            key: Object key within the bucket.
            suffix: Optional file extension suffix (e.g. '.pdf').

        Returns:
            Absolute path to the temporary file.
        """
        temp_dir = settings.S3_STORAGE_TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)

        data = self.download_file(key)

        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=temp_dir)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

        self._log.info(
            "s3_download_to_tempfile",
            key=key,
            temp_path=temp_path,
            size_bytes=len(data),
        )
        return temp_path

    def check_health(self) -> bool:
        """Check if S3/Spaces is reachable."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as exc:
            self._log.error("s3_health_check_failed", error=str(exc))
            return False
