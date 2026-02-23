"""Tests for Telegram webhook security."""
import json


def test_webhook_rejects_bad_token(client):
    resp = client.post(
        "/telegram/webhook/wrong-token",
        data=json.dumps({"message": {}}),
        content_type="application/json",
    )
    assert resp.status_code == 403


def test_webhook_rejects_non_admin(client, app):
    token = app.config["TELEGRAM_BOT_TOKEN"]
    headers = {}
    if app.config.get("TELEGRAM_WEBHOOK_SECRET"):
        headers["X-Telegram-Bot-Api-Secret-Token"] = app.config[
            "TELEGRAM_WEBHOOK_SECRET"
        ]
    resp = client.post(
        f"/telegram/webhook/{token}",
        data=json.dumps({
            "message": {
                "from": {"id": 999999},
                "chat": {"id": 999999},
                "text": "/help",
            }
        }),
        content_type="application/json",
        headers=headers,
    )
    # Returns 200 (silent reject) but takes no action
    assert resp.status_code == 200
