import os


class Config:
    """Base configuration. All values from env vars."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://rangoli:rangoli@localhost:5432/rangoli"
    )
    # Fix Heroku/Railway postgres:// → postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    }

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    TELEGRAM_ADMIN_IDS = [
        int(x.strip())
        for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")
        if x.strip()
    ]

    # S3
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "rangoli-images")
    S3_REGION = os.environ.get("S3_REGION", "auto")
    S3_PUBLIC_URL = os.environ.get("S3_PUBLIC_URL", "")

    # Gemini AI
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # App
    APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

    # Defaults for settings seed
    DEFAULT_USD_FX_RATE = os.environ.get("DEFAULT_USD_FX_RATE", "83.00")
    DEFAULT_WHATSAPP_NUMBER = os.environ.get(
        "DEFAULT_WHATSAPP_NUMBER", "919876543210"
    )


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///rangoli_dev.db"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite doesn't support pool_size
    REDIS_URL = os.environ.get("REDIS_URL", "")  # optional in dev


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def init_app(cls, app):
        import logging
        import sys

        assert app.config["SECRET_KEY"] != "dev-secret-change-me", (
            "SECRET_KEY must be set in production"
        )
        assert app.config["TELEGRAM_BOT_TOKEN"], (
            "TELEGRAM_BOT_TOKEN must be set"
        )

        # Stream logs to stdout for Railway
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Rangoli Boutique starting in production mode")


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    REDIS_URL = "redis://localhost:6379/1"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
