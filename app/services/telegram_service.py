import json
import logging
import httpx
from flask import current_app

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _url(method):
    return BASE_URL.format(token=current_app.config["TELEGRAM_BOT_TOKEN"], method=method)


def _post(method, **kwargs):
    """Make a POST request to Telegram Bot API."""
    resp = httpx.post(_url(method), **kwargs)
    data = resp.json()
    if not data.get("ok"):
        logger.error("Telegram API error: %s", data)
        raise RuntimeError(f"Telegram API error: {data.get('description', 'unknown')}")
    return data.get("result")


def send_message(chat_id, text, reply_markup=None, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return _post("sendMessage", data=payload)


def send_photo(chat_id, photo_url, caption=None, reply_markup=None):
    """Send a photo by URL with optional caption and inline keyboard."""
    payload = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return _post("sendPhoto", data=payload)


def edit_message_caption(chat_id, message_id, caption, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return _post("editMessageCaption", data=payload)


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _post("answerCallbackQuery", data=payload)


def get_file(file_id):
    """Get file info to construct download URL."""
    return _post("getFile", data={"file_id": file_id})


def download_file(file_path):
    """Download a file from Telegram servers."""
    token = current_app.config["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    resp = httpx.get(url)
    resp.raise_for_status()
    return resp.content


def set_webhook(url, secret_token=None):
    """Register the webhook URL with Telegram."""
    payload = {"url": url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _post("setWebhook", data=payload)
