"""Telegram message and callback query handlers."""
import logging
import re
from flask import current_app
from rq import Retry

from app.extensions import db, task_queue
from app.models.product import Product
from app.models.image import Image
from app.models.settings import Settings
from app.models.audit_log import AuditLog
from app.services import (
    product_service,
    telegram_service,
    storage_service,
    image_service,
)
from app.blueprints.telegram.keyboards import approval_keyboard, fallback_keyboard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

def handle_message(message):
    """Route incoming Telegram messages to appropriate handler."""
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    # Photo with caption → create draft
    if "photo" in message:
        _handle_photo(message, chat_id, user_id)
        return

    text = message.get("text", "").strip()
    if not text:
        return

    # Command routing
    if text.startswith("/setrate"):
        _handle_set_rate(text, chat_id, user_id)
    elif text.startswith("/setwhatsapp"):
        _handle_set_whatsapp(text, chat_id, user_id)
    elif text.startswith("/soldout"):
        _handle_sold_out(text, chat_id, user_id)
    elif text.startswith("/hide "):
        _handle_hide(text, chat_id, user_id)
    elif text.startswith("/unhide"):
        _handle_unhide(text, chat_id, user_id)
    elif text.startswith("/editprice"):
        _handle_edit_price(text, chat_id, user_id)
    elif text.startswith("/addinsta"):
        _handle_add_insta(text, chat_id, user_id)
    elif text.startswith("/removeinsta"):
        _handle_remove_insta(text, chat_id, user_id)
    elif text.startswith("/listinsta"):
        _handle_list_insta(chat_id)
    elif text.startswith("/stats"):
        _handle_stats(chat_id)
    elif text.startswith("/help") or text.startswith("/start"):
        _handle_help(chat_id)
    else:
        telegram_service.send_message(
            chat_id, "Unknown command. Send /help for available commands."
        )


def _handle_photo(message, chat_id, user_id):
    """Process photo + caption → create draft product."""
    caption = message.get("caption", "")
    if not caption:
        telegram_service.send_message(
            chat_id,
            "Please include a caption with metadata.\n\n"
            "Format:\n"
            "Title: Dress Name\n"
            "Price: 12500\n"
            "Category: saree\n"
            "Tags: silk, red, wedding\n"
            "Variants: Size: Free Size; Color: Red",
        )
        return

    metadata = product_service.parse_caption(caption)
    if not metadata["title"] or not metadata["price"]:
        telegram_service.send_message(
            chat_id, "Caption must include at least Title and Price."
        )
        return

    # Get highest-resolution photo
    photo = message["photo"][-1]
    file_info = telegram_service.get_file(photo["file_id"])
    image_bytes = telegram_service.download_file(file_info["file_path"])

    # Validate and sanitize image
    try:
        image_bytes = image_service.validate_image(image_bytes)
    except ValueError as e:
        telegram_service.send_message(chat_id, f"Image error: {e}")
        return

    # Create the product draft
    product, ai_image = product_service.create_draft(
        metadata=metadata,
        original_storage_key="",  # placeholder
        original_url="",
        chat_id=chat_id,
        admin_id=user_id,
    )

    # Store image bytes in original image record (DB storage)
    storage_key = f"originals/{product.dress_id}/v1.jpg"
    original = product.images.filter_by(type="ORIGINAL").first()
    original.storage_key = storage_key
    original.image_data = image_bytes
    original.status = "READY"

    app_url = current_app.config.get("APP_URL", "").rstrip("/")
    original.url = f"{app_url}/img/{original.id}"

    # Delete the AI image placeholder — publish with original directly
    if ai_image:
        db.session.delete(ai_image)

    product.status = "PUBLISHED"
    db.session.commit()

    telegram_service.send_message(
        chat_id,
        f"✅ Published: {product.dress_id}\n"
        f"Title: {product.title}\n"
        f"Price: INR {metadata['price']:,}\n\n"
        f"Live on the website now!",
    )


def _handle_set_rate(text, chat_id, user_id):
    """Set USD FX rate. Usage: /setrate 83.50"""
    match = re.search(r"[\d.]+", text.split(maxsplit=1)[-1] if " " in text else "")
    if not match:
        telegram_service.send_message(chat_id, "Usage: /setrate 83.50")
        return

    rate = float(match.group())
    if rate <= 0 or rate > 500:
        telegram_service.send_message(chat_id, "Rate must be between 0 and 500.")
        return

    Settings.set("usd_fx_rate", str(rate))
    db.session.add(
        AuditLog(admin_id=user_id, action="SET_USD_RATE", payload={"rate": rate})
    )
    db.session.commit()
    telegram_service.send_message(chat_id, f"USD rate set to {rate}")


def _handle_set_whatsapp(text, chat_id, user_id):
    """Set WhatsApp number. Usage: /setwhatsapp 919876543210"""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        telegram_service.send_message(chat_id, "Usage: /setwhatsapp 919876543210")
        return

    number = re.sub(r"[^\d]", "", parts[1])
    if len(number) < 10:
        telegram_service.send_message(chat_id, "Invalid phone number.")
        return

    Settings.set("whatsapp_number", number)
    db.session.add(
        AuditLog(
            admin_id=user_id, action="SET_WHATSAPP", payload={"number": number}
        )
    )
    db.session.commit()
    telegram_service.send_message(chat_id, f"WhatsApp number set to {number}")


def _handle_sold_out(text, chat_id, user_id):
    """Mark product sold out. Usage: /soldout D-1042"""
    dress_id = _extract_dress_id(text)
    if not dress_id:
        telegram_service.send_message(chat_id, "Usage: /soldout D-1042")
        return

    product = product_service.mark_sold_out(dress_id, user_id)
    if product:
        telegram_service.send_message(chat_id, f"{dress_id} marked as SOLD OUT")
    else:
        telegram_service.send_message(chat_id, f"{dress_id} not found or not in valid state.")


def _handle_hide(text, chat_id, user_id):
    dress_id = _extract_dress_id(text)
    if not dress_id:
        telegram_service.send_message(chat_id, "Usage: /hide D-1042")
        return
    product = product_service.hide_product(dress_id, user_id)
    if product:
        telegram_service.send_message(chat_id, f"{dress_id} hidden from catalog")
    else:
        telegram_service.send_message(chat_id, f"{dress_id} not found or not PUBLISHED.")


def _handle_unhide(text, chat_id, user_id):
    dress_id = _extract_dress_id(text)
    if not dress_id:
        telegram_service.send_message(chat_id, "Usage: /unhide D-1042")
        return
    product = product_service.unhide_product(dress_id, user_id)
    if product:
        telegram_service.send_message(chat_id, f"{dress_id} is now visible again")
    else:
        telegram_service.send_message(chat_id, f"{dress_id} not found or not HIDDEN.")


def _handle_edit_price(text, chat_id, user_id):
    """Edit price. Usage: /editprice D-1042 15000"""
    parts = text.split()
    if len(parts) < 3:
        telegram_service.send_message(chat_id, "Usage: /editprice D-1042 15000")
        return
    dress_id = parts[1].upper()
    try:
        price = int(re.sub(r"[^\d]", "", parts[2]))
    except (ValueError, IndexError):
        telegram_service.send_message(chat_id, "Invalid price.")
        return

    product = product_service.update_price(dress_id, price, user_id)
    if product:
        telegram_service.send_message(
            chat_id, f"{dress_id} price updated to INR {price:,}"
        )
    else:
        telegram_service.send_message(chat_id, f"{dress_id} not found.")


def _handle_add_insta(text, chat_id, user_id):
    """Add Instagram post to catalog. Usage: /addinsta https://www.instagram.com/p/xxx/"""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or "instagram.com" not in parts[1]:
        telegram_service.send_message(
            chat_id,
            "Usage: /addinsta https://www.instagram.com/p/ABC123/\n"
            "Also works with /reel/ URLs.",
        )
        return

    url = parts[1].strip()
    posts = Settings.add_instagram_post(url)
    db.session.add(
        AuditLog(admin_id=user_id, action="ADD_INSTAGRAM", payload={"url": url})
    )
    db.session.commit()
    telegram_service.send_message(
        chat_id, f"Instagram post added ({len(posts)} total on catalog)."
    )


def _handle_remove_insta(text, chat_id, user_id):
    """Remove Instagram post. Usage: /removeinsta 1  or  /removeinsta <url>"""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        telegram_service.send_message(
            chat_id, "Usage: /removeinsta 1  (number from /listinsta)"
        )
        return

    removed = Settings.remove_instagram_post(parts[1])
    if removed:
        db.session.add(
            AuditLog(
                admin_id=user_id, action="REMOVE_INSTAGRAM", payload={"url": removed}
            )
        )
        db.session.commit()
        telegram_service.send_message(chat_id, f"Removed: {removed}")
    else:
        telegram_service.send_message(chat_id, "Post not found. Use /listinsta to see current posts.")


def _handle_list_insta(chat_id):
    """List all Instagram embeds on catalog."""
    posts = Settings.get_instagram_posts()
    if not posts:
        telegram_service.send_message(
            chat_id, "No Instagram posts on catalog.\nAdd with: /addinsta <url>"
        )
        return
    lines = [f"  {i+1}. {url}" for i, url in enumerate(posts)]
    telegram_service.send_message(
        chat_id,
        f"Instagram posts ({len(posts)}):\n" + "\n".join(lines)
        + "\n\nRemove with: /removeinsta <number>",
    )


def _handle_stats(chat_id):
    stats = product_service.get_stats()
    lines = [f"  {status}: {count}" for status, count in sorted(stats.items())]
    total = sum(stats.values())
    telegram_service.send_message(
        chat_id,
        f"Product Stats (total: {total}):\n" + "\n".join(lines) if lines else "No products yet.",
    )


def _handle_help(chat_id):
    telegram_service.send_message(
        chat_id,
        "Rangoli Boutique Admin Bot\n\n"
        "Add item: Send a photo with caption:\n"
        "  Title: Name\n"
        "  Price: 12500\n"
        "  Category: saree\n"
        "  Tags: silk, red\n"
        "  Variants: Size: Free Size; Color: Red\n\n"
        "Commands:\n"
        "  /soldout D-1042 — Mark sold out\n"
        "  /hide D-1042 — Hide from catalog\n"
        "  /unhide D-1042 — Show in catalog\n"
        "  /editprice D-1042 15000 — Change price\n"
        "  /setrate 83.50 — Set USD exchange rate\n"
        "  /setwhatsapp 919876543210 — Set WhatsApp\n"
        "  /addinsta <url> — Add Instagram post to catalog\n"
        "  /removeinsta <#> — Remove Instagram post\n"
        "  /listinsta — List Instagram posts\n"
        "  /stats — Product counts by status\n"
        "  /help — This message",
    )


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

def handle_callback_query(callback_query):
    """Handle inline keyboard button presses."""
    data = callback_query.get("data", "")
    user_id = callback_query["from"]["id"]
    cb_id = callback_query["id"]

    if ":" not in data:
        telegram_service.answer_callback_query(cb_id, "Invalid action")
        return

    action, product_id_str = data.split(":", 1)

    try:
        product_id = int(product_id_str)
    except ValueError:
        telegram_service.answer_callback_query(cb_id, "Invalid product ID")
        return

    product = db.session.get(Product, product_id)
    if not product:
        telegram_service.answer_callback_query(cb_id, "Product not found")
        return

    if action == "approve":
        _cb_approve(product, user_id, cb_id)
    elif action == "regen":
        _cb_regenerate(product, user_id, cb_id)
    elif action == "pub_orig":
        _cb_publish_original(product, user_id, cb_id)
    elif action == "discard":
        _cb_discard(product, user_id, cb_id)
    elif action == "edit_meta":
        _cb_edit_metadata(product, user_id, cb_id)
    else:
        telegram_service.answer_callback_query(cb_id, "Unknown action")


def _cb_approve(product, admin_id, cb_id):
    """Approve & Publish with AI image."""
    if product.status != "DRAFT":
        telegram_service.answer_callback_query(cb_id, "Not in DRAFT state")
        return

    # Update URLs to use Flask endpoint (DB-backed)
    app_url = current_app.config.get("APP_URL", "").rstrip("/")
    original = product.original_image
    ai_img = product.ai_image

    if original:
        original.url = f"{app_url}/img/{original.id}"

    if ai_img:
        ai_img.url = f"{app_url}/img/{ai_img.id}"

    product_service.publish_product(
        product.id, admin_id, ai_version=ai_img.version if ai_img else None
    )

    # Update Telegram message
    if product.telegram_message_id:
        try:
            telegram_service.edit_message_caption(
                chat_id=product.telegram_chat_id,
                message_id=product.telegram_message_id,
                caption=f"PUBLISHED: {product.dress_id} — {product.title}",
            )
        except Exception:
            pass  # message may have been deleted

    telegram_service.answer_callback_query(cb_id, f"{product.dress_id} published!")


def _cb_regenerate(product, admin_id, cb_id):
    """Regenerate AI image (new version)."""
    if product.status != "DRAFT":
        telegram_service.answer_callback_query(cb_id, "Not in DRAFT state")
        return

    # Determine next version
    latest_ai = (
        product.images.filter_by(type="AI_GENERATED")
        .order_by(Image.version.desc())
        .first()
    )
    next_version = (latest_ai.version + 1) if latest_ai else 1

    ai_image = Image(
        product_id=product.id,
        type="AI_GENERATED",
        version=next_version,
        storage_key=f"ai/{product.dress_id}/v{next_version}.jpg",
        status="PENDING",
    )
    db.session.add(ai_image)

    db.session.add(
        AuditLog(
            admin_id=admin_id,
            action="REGENERATE_AI",
            product_id=product.id,
            payload={"new_version": next_version},
        )
    )
    db.session.commit()

    original = product.original_image

    task_queue.enqueue(
        "app.workers.ai_generation.generate_ai_image",
        product_id=product.id,
        image_id=ai_image.id,
        original_storage_key=original.storage_key,
        version=next_version,
        job_id=f"ai_gen_{ai_image.id}",
        retry=Retry(max=3, interval=[30, 120, 300]),
    )

    if product.telegram_message_id:
        try:
            telegram_service.edit_message_caption(
                chat_id=product.telegram_chat_id,
                message_id=product.telegram_message_id,
                caption=f"Regenerating AI v{next_version} for {product.dress_id}...",
                reply_markup=None,
            )
        except Exception:
            pass

    telegram_service.answer_callback_query(cb_id, f"Regenerating v{next_version}...")


def _cb_publish_original(product, admin_id, cb_id):
    """Publish with original image only."""
    if product.status != "DRAFT":
        telegram_service.answer_callback_query(cb_id, "Not in DRAFT state")
        return

    app_url = current_app.config.get("APP_URL", "").rstrip("/")
    original = product.original_image
    if original:
        original.url = f"{app_url}/img/{original.id}"

    product_service.publish_original_only(product.id, admin_id)

    if product.telegram_message_id:
        try:
            telegram_service.edit_message_caption(
                chat_id=product.telegram_chat_id,
                message_id=product.telegram_message_id,
                caption=f"PUBLISHED (original): {product.dress_id}",
            )
        except Exception:
            pass

    telegram_service.answer_callback_query(
        cb_id, f"{product.dress_id} published with original!"
    )


def _cb_discard(product, admin_id, cb_id):
    """Discard draft — delete product and images."""
    if product.status != "DRAFT":
        telegram_service.answer_callback_query(cb_id, "Not in DRAFT state")
        return

    dress_id = product.dress_id
    chat_id = product.telegram_chat_id
    message_id = product.telegram_message_id

    storage_keys = product_service.discard_draft(product.id, admin_id)

    # Clean up stored image data
    if storage_keys:
        try:
            storage_service.delete_many(storage_keys)
        except Exception:
            logger.warning("Failed to delete image data for %s", dress_id)

    if message_id:
        try:
            telegram_service.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=f"DISCARDED: {dress_id}",
            )
        except Exception:
            pass

    telegram_service.answer_callback_query(cb_id, f"{dress_id} discarded")


def _cb_edit_metadata(product, admin_id, cb_id):
    """Prompt admin to send metadata edits."""
    telegram_service.answer_callback_query(cb_id, "Send edit commands")
    telegram_service.send_message(
        product.telegram_chat_id,
        f"To edit {product.dress_id}, send:\n"
        f"  /editprice {product.dress_id} <new_price>\n\n"
        f"More edit commands coming soon.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_dress_id(text):
    """Extract dress ID (e.g., D-1042) from command text."""
    match = re.search(r"D-\d+", text, re.IGNORECASE)
    return match.group().upper() if match else None
