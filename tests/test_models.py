"""Tests for database models."""
from app.models.product import Product
from app.models.variant import VariantOption
from app.models.image import Image
from app.models.settings import Settings


def test_product_creation(db):
    p = Product(
        dress_id="D-9999",
        title="Test Saree",
        price_inr=1250000,  # ₹12,500 in paise
        status="DRAFT",
        categories=["saree"],
        tags=["silk", "red"],
    )
    db.session.add(p)
    db.session.flush()

    assert p.id is not None
    assert p.dress_id == "D-9999"
    assert p.price_inr_display == 12500.0
    assert p.price_usd_display(83.0) == 151  # round(12500/83)


def test_product_visibility(db):
    p = Product(dress_id="D-9998", title="Test", price_inr=100000, status="DRAFT")
    assert not p.is_visible

    p.status = "PUBLISHED"
    assert p.is_visible


def test_variant_option(db):
    p = Product(dress_id="D-9997", title="Test", price_inr=100000, status="DRAFT")
    db.session.add(p)
    db.session.flush()

    v = VariantOption(product_id=p.id, type="Size", value="Free Size", sort_order=0)
    db.session.add(v)
    db.session.flush()

    assert v.id is not None
    assert v.product_id == p.id


def test_image_model(db):
    p = Product(dress_id="D-9996", title="Test", price_inr=100000, status="DRAFT")
    db.session.add(p)
    db.session.flush()

    img = Image(
        product_id=p.id,
        type="ORIGINAL",
        version=1,
        storage_key="originals/D-9996/v1.jpg",
        status="READY",
    )
    db.session.add(img)
    db.session.flush()

    assert img.type == "ORIGINAL"
    assert img.status == "READY"


def test_settings(db):
    Settings.set("test_key", "test_value")
    assert Settings.get("test_key") == "test_value"
    assert Settings.get("missing_key", "default") == "default"
