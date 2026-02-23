import io
import google.generativeai as genai
from PIL import Image as PILImage
from flask import current_app


AI_PROMPT = """Generate a photorealistic studio photograph of an Indian woman wearing \
the exact garment shown in the reference image.

CRITICAL REQUIREMENTS — garment fidelity:
- Preserve the EXACT pattern, color, texture, weave, and embroidery
- Preserve the EXACT drape style, pleating, and silhouette
- Do NOT simplify, stylize, or alter the garment design in any way
- The garment must look identical to the reference — as if photographed on a person

Model and setting:
- Indian woman, age 25-35, medium skin tone, pleasant neutral expression
- Standing pose, slightly angled, hands naturally at sides
- Plain off-white/cream studio backdrop
- Soft diffused lighting, no harsh shadows
- Full body shot showing the complete garment

NEGATIVE CONSTRAINTS — strictly avoid:
- No nudity or revealing poses
- No invented logos, text, watermarks, or brand names
- No warped/extra/missing fingers or hands
- No unrealistic body proportions
- No background objects, furniture, or outdoor scenes
- No sunglasses, hats, or accessories not in the original garment
- No color shifts or artistic filters"""


def configure():
    """Configure Gemini with API key."""
    genai.configure(api_key=current_app.config["GEMINI_API_KEY"])


def generate_image(original_image_bytes):
    """Generate AI hero image from original garment photo.

    Args:
        original_image_bytes: bytes of the original garment image

    Returns:
        bytes of the generated image (JPEG)

    Raises:
        Exception on API errors or invalid output
    """
    configure()

    # Load and prepare reference image
    original = PILImage.open(io.BytesIO(original_image_bytes))
    if original.mode != "RGB":
        original = original.convert("RGB")

    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    response = model.generate_content(
        [AI_PROMPT, original],
        generation_config=genai.GenerationConfig(
            response_mime_type="image/jpeg",
        ),
    )

    # Extract image bytes from response
    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates")

    candidate = response.candidates[0]

    # Handle inline image data
    for part in candidate.content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            image_bytes = part.inline_data.data
            # Validate it's actually an image
            img = PILImage.open(io.BytesIO(image_bytes))
            img.verify()
            # Re-encode as high-quality JPEG
            img = PILImage.open(io.BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()

    raise RuntimeError("Gemini response did not contain an image")
