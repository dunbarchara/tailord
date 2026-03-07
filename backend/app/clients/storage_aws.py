import logging

import boto3

from app.clients.storage_client import StorageClient
from app.config import settings

logger = logging.getLogger(__name__)


class S3StorageClient(StorageClient):
    def _client(self):
        return boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
        )

    def generate_upload_url(self, key: str, expires_in: int = 300) -> str:
        logger.debug("Generating S3 presigned PUT URL for key=%s expires_in=%s", key, expires_in)
        url = self._client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_uploads_bucket,
                "Key": key,
                # ContentType intentionally excluded from signature — browser
                # file.type can be empty/mismatched, which causes SignatureDoesNotMatch.
            },
            ExpiresIn=expires_in,
        )
        logger.debug("S3 presigned URL generated for key=%s", key)
        return url

    def download_bytes(self, key: str) -> bytes:
        logger.debug("Downloading S3 object key=%s bucket=%s", key, settings.s3_uploads_bucket)
        response = self._client().get_object(Bucket=settings.s3_uploads_bucket, Key=key)
        data = response["Body"].read()
        logger.debug("Downloaded %d bytes for key=%s", len(data), key)
        return data

    def delete_object(self, key: str) -> None:
        logger.debug("Deleting S3 object key=%s bucket=%s", key, settings.s3_uploads_bucket)
        self._client().delete_object(Bucket=settings.s3_uploads_bucket, Key=key)
        logger.debug("Deleted S3 object key=%s", key)
