#!/usr/bin/env python3
"""Seed sample products for local development."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.product import Product
from app.models.variant import VariantOption
from app.models.image import Image

app = create_app()

SAMPLE_PRODUCTS = [
    {
        "title": "Red Banarasi Silk Saree",
        "price": 12500,
        "categories": ["saree"],
        "tags": ["silk", "banarasi", "red", "wedding", "traditional"],
        "variants": [
            ("Size", "Free Size"),
            ("Color", "Red with Gold Border"),
        ],
    },
    {
        "title": "Navy Blue Anarkali Suit",
        "price": 8500,
        "categories": ["suit"],
        "tags": ["anarkali", "blue", "party", "embroidered"],
        "variants": [
            ("Size", "S"),
            ("Size", "M"),
            ("Size", "L"),
            ("Color", "Navy Blue"),
        ],
    },
    {
        "title": "Pink Georgette Lehenga",
        "price": 22000,
        "categories": ["lehenga"],
        "tags": ["pink", "georgette", "wedding", "bridal", "embroidered"],
        "variants": [
            ("Size", "M"),
            ("Size", "L"),
            ("Color", "Blush Pink"),
        ],
    },
    {
        "title": "Green Cotton Kurti",
        "price": 2200,
        "categories": ["kurti"],
        "tags": ["green", "cotton", "casual", "daily"],
        "variants": [
            ("Size", "S"),
            ("Size", "M"),
            ("Size", "L"),
            ("Size", "XL"),
            ("Color", "Emerald Green"),
        ],
    },
    {
        "title": "Maroon Velvet Gown",
        "price": 18000,
        "categories": ["gown"],
        "tags": ["maroon", "velvet", "party", "evening"],
        "variants": [
            ("Size", "M"),
            ("Size", "L"),
            ("Color", "Maroon"),
        ],
    },
    {
        "title": "Yellow Chanderi Saree",
        "price": 6500,
        "categories": ["saree"],
        "tags": ["yellow", "chanderi", "festive", "lightweight"],
        "variants": [
            ("Size", "Free Size"),
            ("Color", "Mustard Yellow"),
        ],
    },
    {
        "title": "White Chikankari Kurti",
        "price": 3500,
        "categories": ["kurti"],
        "tags": ["white", "chikankari", "lucknowi", "casual"],
        "variants": [
            ("Size", "S"),
            ("Size", "M"),
            ("Size", "L"),
            ("Color", "White"),
        ],
    },
    {
        "title": "Gold Tissue Dupatta",
        "price": 4500,
        "categories": ["dupatta"],
        "tags": ["gold", "tissue", "wedding", "accessory"],
        "variants": [
            ("Size", "Free Size"),
            ("Color", "Gold"),
        ],
    },
]

# Placeholder image — a simple colored SVG data URI won't work for <img> via URL,
# so we use placeholder.com style URLs for demo purposes
COLORS = [
    "c0392b", "2c3e50", "e91e63", "27ae60",
    "8e44ad", "f39c12", "ecf0f1", "f1c40f",
]


def seed():
    with app.app_context():
        if Product.query.first():
            print("Products already exist — skipping seed.")
            return

        for i, item in enumerate(SAMPLE_PRODUCTS):
            seq_num = 1001 + i
            dress_id = f"D-{seq_num}"

            product = Product(
                dress_id=dress_id,
                title=item["title"],
                price_inr=item["price"] * 100,
                categories=item["categories"],
                tags=item["tags"],
                status="PUBLISHED",
            )
            db.session.add(product)
            db.session.flush()

            for j, (vtype, vvalue) in enumerate(item["variants"]):
                db.session.add(
                    VariantOption(
                        product_id=product.id,
                        type=vtype,
                        value=vvalue,
                        sort_order=j,
                    )
                )

            # Create a placeholder image record (no real file)
            color = COLORS[i % len(COLORS)]
            db.session.add(
                Image(
                    product_id=product.id,
                    type="ORIGINAL",
                    version=1,
                    storage_key=f"originals/{dress_id}/v1.jpg",
                    url=f"https://placehold.co/600x800/{color}/fff?text={dress_id}",
                    status="READY",
                )
            )

            print(f"  Created {dress_id}: {item['title']}")

        db.session.commit()
        print(f"\nSeeded {len(SAMPLE_PRODUCTS)} products.")


if __name__ == "__main__":
    seed()
