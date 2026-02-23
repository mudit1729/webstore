#!/usr/bin/env python3
"""One-time script to register Telegram webhook.

Usage:
    python scripts/set_webhook.py

Reads config from environment variables.
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    app_url = os.environ.get("APP_URL", "").rstrip("/")

    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not app_url:
        print("Error: APP_URL not set")
        sys.exit(1)

    webhook_url = f"{app_url}/telegram/webhook/{token}"

    payload = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret

    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=payload,
    )
    data = resp.json()

    if data.get("ok"):
        print(f"Webhook registered: {webhook_url}")
        print(f"Response: {data.get('description')}")
    else:
        print(f"Error: {data}")
        sys.exit(1)


if __name__ == "__main__":
    main()
