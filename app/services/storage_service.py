import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=current_app.config["S3_ENDPOINT_URL"] or None,
        aws_access_key_id=current_app.config["S3_ACCESS_KEY"],
        aws_secret_access_key=current_app.config["S3_SECRET_KEY"],
        region_name=current_app.config["S3_REGION"],
        config=BotoConfig(signature_version="s3v4"),
    )


def upload(storage_key, data, content_type="image/jpeg", private=True):
    """Upload bytes to S3."""
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    acl = "private" if private else "public-read"

    client.put_object(
        Bucket=bucket,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
        ACL=acl,
    )


def download(storage_key):
    """Download file bytes from S3."""
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    response = client.get_object(Bucket=bucket, Key=storage_key)
    return response["Body"].read()


def get_signed_url(storage_key, expires_in=900):
    """Generate a pre-signed URL (default 15 min)."""
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": storage_key},
        ExpiresIn=expires_in,
    )


def get_public_url(storage_key):
    """Return the public CDN URL for a storage key."""
    base = current_app.config["S3_PUBLIC_URL"].rstrip("/")
    return f"{base}/{storage_key}"


def make_public(storage_key):
    """Change an object's ACL to public-read."""
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    client.put_object_acl(
        Bucket=bucket,
        Key=storage_key,
        ACL="public-read",
    )


def delete(storage_key):
    """Delete an object from S3."""
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    client.delete_object(Bucket=bucket, Key=storage_key)


def delete_many(storage_keys):
    """Delete multiple objects from S3."""
    if not storage_keys:
        return
    client = _get_client()
    bucket = current_app.config["S3_BUCKET_NAME"]
    objects = [{"Key": k} for k in storage_keys]
    client.delete_objects(
        Bucket=bucket,
        Delete={"Objects": objects},
    )
