"""Tests for public web routes."""

import app.extensions as ext
from app.models.image import Image
from app.models.product import Product


def test_catalog_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Rangoli Boutique" in resp.data


def test_product_404(client):
    resp = client.get("/d/D-0000")
    assert resp.status_code == 404


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.get_json()
    assert "status" in data


def test_health_does_not_leak_internal_errors(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("database password leaked")

    monkeypatch.setattr(ext.db.session, "execute", boom)

    resp = client.get("/health")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["db"] == "error"
    assert "password" not in str(data).lower()


def test_draft_images_are_not_public(client, db):
    product = Product(
        dress_id="D-7777",
        title="Private Draft",
        price_inr=100000,
        status="DRAFT",
    )
    db.session.add(product)
    db.session.flush()

    image = Image(
        product_id=product.id,
        type="ORIGINAL",
        version=1,
        storage_key="originals/D-7777/v1.jpg",
        status="READY",
        image_data=b"fake-jpeg-bytes",
    )
    db.session.add(image)
    db.session.commit()

    resp = client.get(f"/img/{image.id}")
    assert resp.status_code == 404
