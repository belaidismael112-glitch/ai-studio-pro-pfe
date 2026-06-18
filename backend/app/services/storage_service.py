"""Object storage service (S3/R2/MinIO) with signed URLs."""

from __future__ import annotations

import io
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # boto3 is optional unless S3/R2 storage is configured
    boto3 = None
    Config = None
    BotoCoreError = ClientError = Exception

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StoredObject:
    key: str
    signed_url: str
    content_type: Optional[str] = None


class StorageService:
    """Uploads generated assets to object storage and returns signed URLs."""

    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET_NAME
        self.enabled = bool(
            self.bucket
            and settings.S3_ACCESS_KEY_ID
            and settings.S3_SECRET_ACCESS_KEY
        )

        if not self.enabled or boto3 is None:
            if self.enabled and boto3 is None:
                logger.warning("S3/R2 storage configured but boto3 is not installed; falling back to direct/local URLs")
            self.enabled = False
            self._client = None
            return

        self._client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )

    def _make_key(self, user_id: int, kind: str, ext: str) -> str:
        ext = ext.lstrip(".")
        return f"users/{user_id}/{kind}/{uuid.uuid4().hex}.{ext}"

    def presign_get(self, key: str) -> Optional[str]:
        if not self.enabled or not self._client:
            return None
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=settings.SIGNED_URL_EXPIRE_SECONDS,
            )
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to generate signed URL for {key}: {e}")
            return None

    async def upload_from_url(
        self,
        *,
        user_id: int,
        kind: str,
        source_url: str,
        filename_hint: Optional[str] = None,
        content_type_hint: Optional[str] = None,
    ) -> Optional[StoredObject]:
        """Download a remote asset and upload it to storage."""

        if not self.enabled or not self._client:
            return None

        # Determine extension
        ext = "bin"
        if filename_hint and "." in filename_hint:
            ext = filename_hint.rsplit(".", 1)[-1]
        elif "." in source_url.split("?")[0]:
            ext = source_url.split("?")[0].rsplit(".", 1)[-1]

        key = self._make_key(user_id, kind, ext)

        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            r = await client.get(source_url)
            r.raise_for_status()
            content = r.content
            content_type = (
                content_type_hint
                or r.headers.get("content-type")
                or "application/octet-stream"
            )

        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload object to storage: {e}")
            return None

        signed = self.presign_get(key)
        if not signed:
            return None
        return StoredObject(key=key, signed_url=signed, content_type=content_type)


storage_service = StorageService()
