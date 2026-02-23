"""Telegram inline keyboard builders."""


def approval_keyboard(product_id):
    """Build inline keyboard for draft approval preview."""
    return {
        "inline_keyboard": [
            [
                {"text": "Approve & Publish", "callback_data": f"approve:{product_id}"},
                {"text": "Regenerate", "callback_data": f"regen:{product_id}"},
            ],
            [
                {"text": "Edit Metadata", "callback_data": f"edit_meta:{product_id}"},
                {"text": "Publish Original Only", "callback_data": f"pub_orig:{product_id}"},
            ],
            [
                {"text": "Discard Draft", "callback_data": f"discard:{product_id}"},
            ],
        ]
    }


def fallback_keyboard(product_id):
    """Keyboard shown when AI generation fails."""
    return {
        "inline_keyboard": [
            [
                {"text": "Publish Original Only", "callback_data": f"pub_orig:{product_id}"},
                {"text": "Retry AI", "callback_data": f"regen:{product_id}"},
            ],
            [
                {"text": "Discard Draft", "callback_data": f"discard:{product_id}"},
            ],
        ]
    }
