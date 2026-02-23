"""RQ worker job: generate AI hero image for a product."""
import logging
from app import create_app
from flask import current_app, has_app_context
from app.extensions import db, redis_client
from app.models.product import Product
from app.models.image import Image
from app.models.settings import Settings
from app.services import ai_service, storage_service, telegram_service
from app.blueprints.telegram.keyboards import approval_keyboard, fallback_keyboard

logger = logging.getLogger(__name__)

_worker_app = None


def _get_app():
    """Return an app instance for worker execution.

    Reuse the current app when already inside an app context (tests/CLI),
    otherwise lazily create the worker app once.
    """
    global _worker_app
    if has_app_context():
        return current_app._get_current_object()
    if _worker_app is None:
        _worker_app = create_app()
    return _worker_app


def generate_ai_image(product_id, image_id, original_storage_key, version):
    """Generate an AI image for a product and send preview to admin.

    This job is enqueued by the Telegram handler when a draft is created
    or when an admin requests regeneration.

    Idempotency: checks image status before proceeding.
    Distributed lock: prevents duplicate work on the same image.
    """
    app = _get_app()
    with app.app_context():
        image = db.session.get(Image, image_id)
        if not image:
            logger.error("Image record %d not found", image_id)
            return

        # Idempotency: already done
        if image.status == "READY":
            logger.info("Image %d already READY, skipping", image_id)
            return

        # Distributed lock
        lock_key = f"ai_gen:{image_id}"
        lock = redis_client.lock(lock_key, timeout=600)
        if not lock.acquire(blocking=False):
            logger.info("Lock held for image %d, skipping", image_id)
            return

        try:
            product = db.session.get(Product, product_id)
            if not product:
                logger.error("Product %d not found", product_id)
                return

            # Download original image from DB
            original = product.images.filter_by(type="ORIGINAL", status="READY").first()
            if not original or not original.image_data:
                raise ValueError("Original image not found in database")
            original_bytes = original.image_data

            # Generate AI image
            logger.info(
                "Generating AI image for %s v%d", product.dress_id, version
            )
            ai_bytes = ai_service.generate_image(original_bytes)

            # Store AI image bytes in database
            image.image_data = ai_bytes

            # Update image record with URL
            image.url = f"/img/{image.id}"
            image.status = "READY"
            db.session.commit()

            logger.info(
                "AI image ready for %s v%d", product.dress_id, version
            )

            # Send preview card to admin
            _send_preview(product)

        except Exception as e:
            logger.exception(
                "AI generation failed for product %d image %d",
                product_id,
                image_id,
            )
            image.status = "FAILED"
            db.session.commit()

            # Notify admin on failure
            product = db.session.get(Product, product_id)
            if product and product.telegram_chat_id:
                try:
                    telegram_service.send_message(
                        chat_id=product.telegram_chat_id,
                        text=(
                            f"AI generation failed for {product.dress_id} "
                            f"(v{version}).\nError: {str(e)[:200]}\n\n"
                            f"You can retry or publish with original image."
                        ),
                        reply_markup=fallback_keyboard(product.id),
                    )
                except Exception:
                    logger.exception("Failed to notify admin of AI failure")

            raise  # let RQ handle retry

        finally:
            try:
                lock.release()
            except Exception:
                pass  # lock may have expired


def _send_preview(product):
    """Send original + AI preview images with approval keyboard."""
    original = product.original_image
    ai_img = product.ai_image

    if not original or not ai_img:
        return

    usd_rate = Settings.get_usd_rate()
    price_inr = product.price_inr_display
    price_usd = product.price_usd_display(usd_rate)

    categories_str = ", ".join(product.categories) if product.categories else "—"
    tags_str = ", ".join(product.tags) if product.tags else "—"

    caption = (
        f"{product.dress_id}: {product.title}\n"
        f"Price: INR {price_inr:,.0f} (~${price_usd})\n"
        f"Categories: {categories_str}\n"
        f"Tags: {tags_str}\n"
        f"AI: v{ai_img.version}"
    )

    # Send original photo first
    telegram_service.send_photo(
        chat_id=product.telegram_chat_id,
        photo_url=original.url,
        caption=f"Original — {product.dress_id}",
    )

    # Send AI photo with approval keyboard
    result = telegram_service.send_photo(
        chat_id=product.telegram_chat_id,
        photo_url=ai_img.url,
        caption=caption,
        reply_markup=approval_keyboard(product.id),
    )

    # Store message ID for later editing
    if result and "message_id" in result:
        product.telegram_message_id = result["message_id"]
        db.session.commit()
