"""Public-facing catalog and product pages."""
from urllib.parse import quote
from flask import render_template, request, abort
from app.blueprints.public import public_bp
from app.services.product_service import get_published_products, get_product_by_dress_id
from app.models.settings import Settings


@public_bp.route("/")
def catalog():
    """Catalog page with filters."""
    category = request.args.get("category")
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    color = request.args.get("color")
    size = request.args.get("size")
    sort = request.args.get("sort", "newest")
    page = request.args.get("page", 1, type=int)

    pagination = get_published_products(
        category=category,
        min_price=min_price,
        max_price=max_price,
        color=color,
        size=size,
        sort=sort,
        page=page,
        per_page=24,
    )

    usd_rate = Settings.get_usd_rate()
    instagram_posts = Settings.get_instagram_posts()

    return render_template(
        "catalog.html",
        products=pagination.items,
        pagination=pagination,
        usd_rate=usd_rate,
        instagram_posts=instagram_posts,
        filters={
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "color": color,
            "size": size,
            "sort": sort,
        },
    )


@public_bp.route("/d/<dress_id>")
def product_detail(dress_id):
    """Product detail page."""
    product = get_product_by_dress_id(dress_id)

    if not product or product.status not in ("PUBLISHED", "SOLD_OUT"):
        abort(404)

    usd_rate = Settings.get_usd_rate()
    whatsapp_number = Settings.get_whatsapp_number()
    app_url = request.host_url.rstrip("/")

    # Build WhatsApp link
    page_url = f"{app_url}/d/{product.dress_id}"
    whatsapp_link = build_whatsapp_link(
        phone=whatsapp_number,
        dress_id=product.dress_id,
        variant_text="[selected variant]",
        page_url=page_url,
    )

    return render_template(
        "product.html",
        product=product,
        usd_rate=usd_rate,
        whatsapp_number=whatsapp_number,
        whatsapp_link=whatsapp_link,
        page_url=page_url,
    )


def build_whatsapp_link(phone, dress_id, variant_text, page_url):
    """Build WhatsApp deep link with pre-filled message."""
    message = (
        f"Hi Poonam Jain, I want Dress {dress_id} from Rangoli Boutique.\n"
        f"Variant: {variant_text}\n"
        f"Ship to: [your city, country]\n"
        f"Link: {page_url}"
    )
    return f"https://wa.me/{phone}?text={quote(message)}"
