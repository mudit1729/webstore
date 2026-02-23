"""Flask CLI commands for admin operations."""
import click
from flask import current_app


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables and seed default settings."""
        from app.extensions import db
        from app.models.settings import Settings

        # Create sequence for dress IDs (Postgres only)
        db_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        if "postgresql" in db_uri:
            db.session.execute(
                db.text(
                    "CREATE SEQUENCE IF NOT EXISTS dress_id_seq START WITH 1001"
                )
            )
            db.session.commit()

        # Seed default settings
        defaults = {
            "usd_fx_rate": current_app.config["DEFAULT_USD_FX_RATE"],
            "whatsapp_number": current_app.config["DEFAULT_WHATSAPP_NUMBER"],
        }
        for key, value in defaults.items():
            existing = Settings.query.get(key)
            if not existing:
                db.session.add(Settings(key=key, value=str(value)))
        db.session.commit()

        click.echo("Database initialized with default settings.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Seed demo products and Instagram posts (idempotent)."""
        import json
        from app.extensions import db
        from app.models.product import Product
        from app.models.settings import Settings

        # Only seed if no products exist yet
        if Product.query.first():
            click.echo("Products already exist — skipping demo seed.")
            return

        demo_products = [
            ("D-1001", "Red Banarasi Silk Saree", 1250000, ["saree"], ["red", "silk", "banarasi", "wedding"]),
            ("D-1002", "Navy Blue Anarkali Suit", 850000, ["suit"], ["blue", "anarkali", "party"]),
            ("D-1003", "Pink Georgette Lehenga", 2200000, ["lehenga"], ["pink", "georgette", "bridal"]),
            ("D-1004", "Green Cotton Kurti", 220000, ["kurti"], ["green", "cotton", "casual"]),
            ("D-1005", "Maroon Velvet Gown", 1800000, ["gown"], ["maroon", "velvet", "party"]),
            ("D-1006", "Yellow Chanderi Saree", 650000, ["saree"], ["yellow", "chanderi"]),
            ("D-1007", "White Chikankari Kurti", 350000, ["kurti"], ["white", "chikankari", "lucknow"]),
            ("D-1008", "Gold Tissue Dupatta", 450000, ["dupatta"], ["gold", "tissue"]),
        ]
        for dress_id, title, price, cats, tags in demo_products:
            p = Product(
                dress_id=dress_id,
                title=title,
                price_inr=price,
                categories=cats,
                tags=tags,
                status="PUBLISHED",
            )
            db.session.add(p)
        db.session.commit()
        click.echo(f"Seeded {len(demo_products)} demo products.")

        # Seed Instagram posts
        if not Settings.get_instagram_posts():
            insta_posts = [
                "https://www.instagram.com/p/DVDiqdckjU5",
                "https://www.instagram.com/p/DVBh-KXkrRV",
                "https://www.instagram.com/p/DU-TdZID4OZ",
                "https://www.instagram.com/p/DU7lIfnkrEJ",
                "https://www.instagram.com/p/DU7ke1uEjv4",
                "https://www.instagram.com/p/DU7gxJxkgC9",
            ]
            Settings.set("instagram_posts", json.dumps(insta_posts))
            db.session.commit()
            click.echo(f"Seeded {len(insta_posts)} Instagram posts.")

    @app.cli.command("seed-admin")
    @click.argument("telegram_user_id", type=int)
    def seed_admin(telegram_user_id):
        """Print instructions for adding an admin Telegram user ID."""
        click.echo(
            f"Add {telegram_user_id} to the TELEGRAM_ADMIN_IDS environment variable.\n"
            f"Current admins: {current_app.config['TELEGRAM_ADMIN_IDS']}"
        )

    @app.cli.command("set-webhook")
    def set_webhook():
        """Register Telegram webhook URL."""
        from app.services.telegram_service import set_webhook

        token = current_app.config["TELEGRAM_BOT_TOKEN"]
        secret = current_app.config["TELEGRAM_WEBHOOK_SECRET"]
        app_url = current_app.config["APP_URL"].rstrip("/")
        webhook_url = f"{app_url}/telegram/webhook/{token}"

        result = set_webhook(webhook_url, secret_token=secret)
        click.echo(f"Webhook set: {result}")

    @app.cli.command("create-product")
    @click.option("--title", required=True)
    @click.option("--price", required=True, type=int, help="Price in INR")
    @click.option("--category", default="")
    @click.option("--tags", default="")
    def create_product(title, price, category, tags):
        """Create a product directly (for testing)."""
        from app.services.product_service import generate_dress_id
        from app.models.product import Product
        from app.extensions import db

        dress_id = generate_dress_id()
        product = Product(
            dress_id=dress_id,
            title=title,
            price_inr=price * 100,
            categories=[c.strip() for c in category.split(",") if c.strip()],
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            status="DRAFT",
        )
        db.session.add(product)
        db.session.commit()
        click.echo(f"Created: {dress_id} — {title} — INR {price}")

    @app.cli.command("stats")
    def stats():
        """Show product statistics."""
        from app.services.product_service import get_stats

        s = get_stats()
        total = sum(s.values())
        click.echo(f"Total products: {total}")
        for status, count in sorted(s.items()):
            click.echo(f"  {status}: {count}")
