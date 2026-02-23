import logging
import hmac
from flask import request, current_app
from app.blueprints.telegram import telegram_bp
from app.blueprints.telegram.handlers import handle_message, handle_callback_query

logger = logging.getLogger(__name__)


@telegram_bp.route("/webhook/<token>", methods=["POST"])
def webhook(token):
    """Telegram webhook endpoint.

    Security:
    - Token in URL must match TELEGRAM_BOT_TOKEN
    - X-Telegram-Bot-Api-Secret-Token header must match TELEGRAM_WEBHOOK_SECRET
    - Sender must be in TELEGRAM_ADMIN_IDS allowlist
    """
    # Verify token in URL
    expected_token = current_app.config["TELEGRAM_BOT_TOKEN"]
    if not expected_token or not hmac.compare_digest(token, expected_token):
        return "", 403

    # Verify secret header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected_secret = current_app.config["TELEGRAM_WEBHOOK_SECRET"]
    if expected_secret and not hmac.compare_digest(secret, expected_secret):
        logger.warning("Invalid webhook secret header")
        return "", 403

    update = request.get_json(silent=True)
    if not update:
        return "", 400

    try:
        # Check admin allowlist
        user_id = _extract_user_id(update)
        if user_id not in current_app.config["TELEGRAM_ADMIN_IDS"]:
            logger.info("Rejected non-admin user: %s", user_id)
            return "", 200  # silent reject — return 200 so Telegram doesn't retry

        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            handle_callback_query(update["callback_query"])

    except Exception:
        logger.exception("Error processing Telegram update")
        # Return 200 to prevent Telegram from retrying on our errors
        # The error is logged for debugging

    return "", 200


def _extract_user_id(update):
    """Extract the Telegram user ID from an update."""
    if "message" in update:
        return update["message"].get("from", {}).get("id")
    if "callback_query" in update:
        return update["callback_query"].get("from", {}).get("id")
    return None
