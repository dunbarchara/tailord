import boto3
from app.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
        endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
    )


def generate_presigned_put_url(s3_key: str, expires: int = 300) -> str:
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_uploads_bucket,
            "Key": s3_key,
            # ContentType intentionally excluded from signature — browser
            # file.type can be empty/mismatched, which causes SignatureDoesNotMatch.
        },
        ExpiresIn=expires,
    )


def download_file_bytes(s3_key: str) -> bytes:
    s3 = get_s3_client()
    response = s3.get_object(Bucket=settings.s3_uploads_bucket, Key=s3_key)
    return response["Body"].read()


def delete_object(s3_key: str) -> None:
    s3 = get_s3_client()
    s3.delete_object(Bucket=settings.s3_uploads_bucket, Key=s3_key)
