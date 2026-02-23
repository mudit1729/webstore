import io
from PIL import Image as PILImage


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_image(image_bytes):
    """Validate and sanitize uploaded image.

    - Checks file size
    - Verifies it's a real image via Pillow
    - Strips EXIF data by re-encoding
    - Converts to JPEG

    Returns:
        Sanitized JPEG bytes

    Raises:
        ValueError on invalid input
    """
    if len(image_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"Image too large: {len(image_bytes)} bytes (max {MAX_FILE_SIZE})")

    try:
        img = PILImage.open(io.BytesIO(image_bytes))
        img.verify()  # verify it's a real image
    except Exception:
        raise ValueError("Invalid image file")

    # Re-open (verify() closes the file) and re-encode to strip EXIF
    img = PILImage.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def create_thumbnail(image_bytes, max_size=(400, 400)):
    """Create a thumbnail for catalog cards."""
    img = PILImage.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail(max_size, PILImage.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()
