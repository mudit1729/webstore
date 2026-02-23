import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app(config_name=None):
    flask_app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV")
        if not config_name:
            # Default to production on managed platforms to avoid accidental
            # debug mode/weak defaults when env selection is omitted.
            if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"):
                config_name = "production"
            else:
                config_name = "development"

    from app.config import config_map

    config_cls = config_map.get(config_name, config_map["development"])
    flask_app.config.from_object(config_cls)

    if hasattr(config_cls, "init_app"):
        config_cls.init_app(flask_app)

    # Initialize extensions
    from app.extensions import db, migrate, init_redis

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    init_redis(flask_app)

    # Import models so Alembic sees them
    from app.models import Product, VariantOption, Image, Settings, AuditLog  # noqa: F401

    # Register blueprints
    from app.blueprints.public import public_bp
    from app.blueprints.telegram import telegram_bp

    flask_app.register_blueprint(public_bp)
    flask_app.register_blueprint(telegram_bp, url_prefix="/telegram")

    # Register CLI commands
    from app.cli import register_cli

    register_cli(flask_app)

    # Serve static files efficiently in production with WhiteNoise
    if not flask_app.debug:
        from whitenoise import WhiteNoise

        flask_app.wsgi_app = WhiteNoise(
            flask_app.wsgi_app,
            root=os.path.join(flask_app.static_folder),
            prefix="static/",
            max_age=31536000,  # 1 year cache for hashed assets
        )

    # Health check
    @flask_app.route("/health")
    def health():
        from app.extensions import redis_client

        checks = {"status": "ok"}
        try:
            db.session.execute(db.text("SELECT 1"))
            checks["db"] = "ok"
        except Exception as e:
            flask_app.logger.exception("Health check DB probe failed")
            checks["db"] = "error"
            checks["status"] = "degraded"
        try:
            if redis_client:
                redis_client.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "not configured"
        except Exception as e:
            flask_app.logger.exception("Health check Redis probe failed")
            checks["redis"] = "error"
            checks["status"] = "degraded"
        status_code = 200 if checks["status"] == "ok" else 503
        return checks, status_code

    return flask_app
