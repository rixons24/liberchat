import boto3
from botocore.client import Config as BotoConfig

from app.config import settings

_s3 = boto3.client(
    "s3",
    endpoint_url=settings.media_storage_endpoint,
    aws_access_key_id=settings.media_storage_access_key,
    aws_secret_access_key=settings.media_storage_secret_key,
    config=BotoConfig(signature_version="s3v4"),
)


async def put_object(key: str, data: bytes):
    _s3.put_object(Bucket=settings.media_bucket, Key=key, Body=data)


async def get_signed_url(key: str, expires_in: int = 60) -> str:
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.media_bucket, "Key": key},
        ExpiresIn=expires_in,
    )


async def delete_object(key: str):
    _s3.delete_object(Bucket=settings.media_bucket, Key=key)
