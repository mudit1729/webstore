from datetime import datetime, timezone
from app.extensions import db


class Settings(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def get(key, default=None):
        row = Settings.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = Settings.query.get(key)
        if row:
            row.value = str(value)
        else:
            row = Settings(key=key, value=str(value))
            db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def get_usd_rate():
        return float(Settings.get("usd_fx_rate", "83.00"))

    @staticmethod
    def get_whatsapp_number():
        return Settings.get("whatsapp_number", "919876543210")

    @staticmethod
    def get_instagram_posts():
        """Return list of Instagram post URLs."""
        import json
        raw = Settings.get("instagram_posts", "[]")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def add_instagram_post(url):
        """Add an Instagram post URL. Max 12 posts."""
        import json
        posts = Settings.get_instagram_posts()
        url = url.strip().rstrip("/")
        if "?" in url:
            url = url.split("?")[0]
        if url not in posts:
            posts.insert(0, url)  # newest first
            posts = posts[:12]
            Settings.set("instagram_posts", json.dumps(posts))
        return posts

    @staticmethod
    def remove_instagram_post(url_or_index):
        """Remove by URL substring or 1-based index."""
        import json
        posts = Settings.get_instagram_posts()
        try:
            idx = int(url_or_index) - 1
            if 0 <= idx < len(posts):
                removed = posts.pop(idx)
                Settings.set("instagram_posts", json.dumps(posts))
                return removed
        except (ValueError, TypeError):
            pass
        url_or_index = url_or_index.strip()
        for i, p in enumerate(posts):
            if url_or_index in p:
                removed = posts.pop(i)
                Settings.set("instagram_posts", json.dumps(posts))
                return removed
        return None

    def __repr__(self):
        return f"<Settings {self.key}={self.value}>"
