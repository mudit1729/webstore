from flask import Blueprint

telegram_bp = Blueprint("telegram", __name__)

from app.blueprints.telegram import webhook  # noqa: F401, E402
