import boto3

from app.clients.storage_client import StorageClient
from app.config import settings


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
        return self._client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_uploads_bucket,
                "Key": key,
                # ContentType intentionally excluded from signature — browser
                # file.type can be empty/mismatched, which causes SignatureDoesNotMatch.
            },
            ExpiresIn=expires_in,
        )

    def download_bytes(self, key: str) -> bytes:
        response = self._client().get_object(Bucket=settings.s3_uploads_bucket, Key=key)
        return response["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client().delete_object(Bucket=settings.s3_uploads_bucket, Key=key)
