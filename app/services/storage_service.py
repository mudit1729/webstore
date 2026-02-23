"""Image storage service — stores image bytes in PostgreSQL.

Replaces the previous S3-based storage. All images are stored as BYTEA
in the Image model's `image_data` column and served via Flask endpoint.
"""
from flask import current_app
from app.extensions import db
from app.models.image import Image


def upload(storage_key, data, content_type="image/jpeg", private=True):
    """Store image bytes in the database.

    Finds the Image record by storage_key and saves the bytes.
    """
    image = Image.query.filter_by(storage_key=storage_key).first()
    if image:
        image.image_data = data
        db.session.commit()


def download(storage_key):
    """Retrieve image bytes from the database."""
    image = Image.query.filter_by(storage_key=storage_key).first()
    if image and image.image_data:
        return image.image_data
    raise FileNotFoundError(f"Image not found: {storage_key}")


def get_image_url(image_id):
    """Return the Flask endpoint URL for an image."""
    app_url = current_app.config.get("APP_URL", "").rstrip("/")
    return f"{app_url}/img/{image_id}"


def get_signed_url(storage_key, expires_in=900):
    """Return URL to serve this image (no signing needed with DB storage)."""
    image = Image.query.filter_by(storage_key=storage_key).first()
    if image:
        return get_image_url(image.id)
    return ""


def get_public_url(storage_key):
    """Return the public URL for an image."""
    image = Image.query.filter_by(storage_key=storage_key).first()
    if image:
        return get_image_url(image.id)
    return ""


def make_public(storage_key):
    """No-op — all images served via Flask are public by endpoint."""
    pass


def delete(storage_key):
    """Delete image data for a storage key."""
    image = Image.query.filter_by(storage_key=storage_key).first()
    if image:
        image.image_data = None
        db.session.commit()


def delete_many(storage_keys):
    """Delete image data for multiple storage keys."""
    if not storage_keys:
        return
    images = Image.query.filter(Image.storage_key.in_(storage_keys)).all()
    for image in images:
        image.image_data = None
    db.session.commit()
