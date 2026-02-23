"""Tests for public web routes."""


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
