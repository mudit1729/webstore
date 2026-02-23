import re
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models.product import Product
from app.models.variant import VariantOption
from app.models.image import Image
from app.models.audit_log import AuditLog


def generate_dress_id():
    """Generate next dress ID.

    Uses Postgres sequence in production, fallback to max(id) for SQLite.
    """
    from flask import current_app

    db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if "postgresql" in db_uri:
        result = db.session.execute(db.text("SELECT nextval('dress_id_seq')"))
        seq = result.scalar()
    else:
        # SQLite fallback: use max product id + 1001
        result = db.session.execute(
            db.text("SELECT COALESCE(MAX(id), 0) FROM products")
        )
        seq = result.scalar() + 1001
    return f"D-{seq}"


def parse_caption(caption):
    """Parse Telegram caption into product metadata.

    Expected format:
        Title: Red Banarasi Silk Saree
        Price: 12500
        Category: saree, lehenga
        Tags: silk, banarasi, red, wedding
        Variants: Size: Free Size; Color: Red with Gold Border
        Description: Beautiful handwoven saree...

    Returns dict with parsed fields.
    """
    lines = caption.strip().split("\n")
    data = {
        "title": "",
        "price": 0,
        "categories": [],
        "tags": [],
        "variants": [],
        "description": "",
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith("title:"):
            data["title"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("price:"):
            price_str = line.split(":", 1)[1].strip()
            price_str = re.sub(r"[^\d]", "", price_str)
            data["price"] = int(price_str) if price_str else 0
        elif line.lower().startswith("category:") or line.lower().startswith(
            "categories:"
        ):
            cats = line.split(":", 1)[1].strip()
            data["categories"] = [c.strip().lower() for c in cats.split(",") if c.strip()]
        elif line.lower().startswith("tag:") or line.lower().startswith("tags:"):
            tags = line.split(":", 1)[1].strip()
            data["tags"] = [t.strip().lower() for t in tags.split(",") if t.strip()]
        elif line.lower().startswith("variant:") or line.lower().startswith(
            "variants:"
        ):
            variants_str = line.split(":", 1)[1].strip()
            for part in variants_str.split(";"):
                part = part.strip()
                if ":" in part:
                    vtype, vvalue = part.split(":", 1)
                    data["variants"].append(
                        {"type": vtype.strip(), "value": vvalue.strip()}
                    )
        elif line.lower().startswith("description:") or line.lower().startswith(
            "desc:"
        ):
            data["description"] = line.split(":", 1)[1].strip()

    return data


def create_draft(metadata, original_storage_key, original_url, chat_id, admin_id):
    """Create a DRAFT product with original image and enqueue AI generation."""
    dress_id = generate_dress_id()

    product = Product(
        dress_id=dress_id,
        title=metadata["title"],
        description=metadata.get("description", ""),
        categories=metadata.get("categories", []),
        tags=metadata.get("tags", []),
        price_inr=metadata["price"] * 100,  # convert rupees to paise
        status="DRAFT",
        telegram_chat_id=chat_id,
    )
    db.session.add(product)
    db.session.flush()  # get product.id

    # Create variant options
    for i, variant in enumerate(metadata.get("variants", [])):
        db.session.add(
            VariantOption(
                product_id=product.id,
                type=variant["type"],
                value=variant["value"],
                sort_order=i,
            )
        )

    # Create original image record
    original_image = Image(
        product_id=product.id,
        type="ORIGINAL",
        version=1,
        storage_key=original_storage_key,
        url=original_url,
        status="READY",
    )
    db.session.add(original_image)

    # Create pending AI image record
    ai_storage_key = f"ai/{dress_id}/v1.jpg"
    ai_image = Image(
        product_id=product.id,
        type="AI_GENERATED",
        version=1,
        storage_key=ai_storage_key,
        status="PENDING",
    )
    db.session.add(ai_image)
    db.session.flush()

    # Audit log
    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="CREATE_DRAFT",
            product_id=product.id,
            payload={"dress_id": dress_id, "title": metadata["title"]},
        )
    )

    db.session.commit()
    return product, ai_image


def publish_product(product_id, admin_id, ai_version=None):
    """Transition product from DRAFT → PUBLISHED."""
    product = db.session.get(Product, product_id)
    if not product or product.status != "DRAFT":
        return None

    product.status = "PUBLISHED"
    product.updated_at = datetime.now(timezone.utc)

    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="PUBLISH",
            product_id=product.id,
            payload={"ai_version": ai_version},
        )
    )
    db.session.commit()
    return product


def publish_original_only(product_id, admin_id):
    """Publish with original image only (skip AI)."""
    product = db.session.get(Product, product_id)
    if not product or product.status != "DRAFT":
        return None

    product.status = "PUBLISHED"
    product.updated_at = datetime.now(timezone.utc)

    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="PUBLISH_ORIGINAL_ONLY",
            product_id=product.id,
        )
    )
    db.session.commit()
    return product


def discard_draft(product_id, admin_id):
    """Delete a DRAFT product and all associated images."""
    product = db.session.get(Product, product_id)
    if not product or product.status != "DRAFT":
        return False

    # Collect storage keys for cleanup
    storage_keys = [img.storage_key for img in product.images]

    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="DISCARD",
            product_id=product.id,
            payload={"dress_id": product.dress_id},
        )
    )

    db.session.delete(product)  # cascades to images + variants
    db.session.commit()
    return storage_keys


def mark_sold_out(dress_id, admin_id):
    """Mark product as SOLD_OUT."""
    product = Product.query.filter_by(dress_id=dress_id.upper()).first()
    if not product:
        return None
    if product.status not in ("PUBLISHED", "HIDDEN"):
        return None

    product.status = "SOLD_OUT"
    product.updated_at = datetime.now(timezone.utc)

    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="MARK_SOLD_OUT",
            product_id=product.id,
        )
    )
    db.session.commit()
    return product


def hide_product(dress_id, admin_id):
    product = Product.query.filter_by(dress_id=dress_id.upper()).first()
    if not product or product.status != "PUBLISHED":
        return None
    product.status = "HIDDEN"
    product.updated_at = datetime.now(timezone.utc)
    db.session.add(
        AuditLog(admin_id=admin_id, action="HIDE", product_id=product.id)
    )
    db.session.commit()
    return product


def unhide_product(dress_id, admin_id):
    product = Product.query.filter_by(dress_id=dress_id.upper()).first()
    if not product or product.status != "HIDDEN":
        return None
    product.status = "PUBLISHED"
    product.updated_at = datetime.now(timezone.utc)
    db.session.add(
        AuditLog(admin_id=admin_id, action="UNHIDE", product_id=product.id)
    )
    db.session.commit()
    return product


def update_price(dress_id, new_price_inr, admin_id):
    product = Product.query.filter_by(dress_id=dress_id.upper()).first()
    if not product:
        return None
    old_price = product.price_inr
    product.price_inr = new_price_inr * 100
    product.updated_at = datetime.now(timezone.utc)
    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="EDIT_PRICE",
            product_id=product.id,
            payload={"old_paise": old_price, "new_paise": new_price_inr * 100},
        )
    )
    db.session.commit()
    return product


def get_published_products(
    category=None, min_price=None, max_price=None, color=None, size=None,
    sort="newest", page=1, per_page=24,
):
    """Fetch published products with filters for catalog."""
    query = Product.query.filter_by(status="PUBLISHED")

    if category:
        query = query.filter(Product.categories.contains([category]))
    if min_price is not None:
        query = query.filter(Product.price_inr >= min_price * 100)
    if max_price is not None:
        query = query.filter(Product.price_inr <= max_price * 100)
    if color:
        query = query.filter(Product.tags.contains([color.lower()]))
    if size:
        # Check variant options for size
        query = query.filter(
            Product.id.in_(
                db.session.query(VariantOption.product_id).filter(
                    VariantOption.type.ilike("size"),
                    VariantOption.value.ilike(f"%{size}%"),
                )
            )
        )

    if sort == "newest":
        query = query.order_by(Product.created_at.desc())
    elif sort == "price_asc":
        query = query.order_by(Product.price_inr.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price_inr.desc())

    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_product_by_dress_id(dress_id):
    """Get a single product by dress ID (for product page)."""
    return Product.query.filter_by(dress_id=dress_id.upper()).first()


def get_stats():
    """Product counts by status for /stats command."""
    rows = (
        db.session.query(Product.status, db.func.count(Product.id))
        .group_by(Product.status)
        .all()
    )
    return dict(rows)
