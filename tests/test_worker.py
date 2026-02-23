"""Tests for worker job logic (mocked)."""
from unittest.mock import patch, MagicMock
from app.models.product import Product
from app.models.image import Image


def test_ai_generation_skips_ready_image(app, db):
    """Idempotency: skip if image already READY."""
    with app.app_context():
        p = Product(dress_id="D-8001", title="Test", price_inr=100000, status="DRAFT")
        db.session.add(p)
        db.session.flush()

        img = Image(
            product_id=p.id,
            type="AI_GENERATED",
            version=1,
            storage_key="ai/D-8001/v1.jpg",
            status="READY",  # already done
        )
        db.session.add(img)
        db.session.flush()

        # Import here to avoid app context issues
        with patch("app.workers.ai_generation.ai_service") as mock_ai:
            from app.workers.ai_generation import generate_ai_image
            generate_ai_image(p.id, img.id, "originals/D-8001/v1.jpg", 1)
            # AI service should NOT have been called
            mock_ai.generate_image.assert_not_called()
