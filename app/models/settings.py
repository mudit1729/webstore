from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
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
    def _normalize_instagram_post_url(url):
        """Validate and normalize an Instagram post/reel URL."""
        if not url or not isinstance(url, str):
            raise ValueError("Instagram URL is required.")

        candidate = url.strip()
        parts = urlsplit(candidate)

        if parts.scheme.lower() != "https":
            raise ValueError("Instagram URL must use https://")
        if parts.username or parts.password:
            raise ValueError("Instagram URL must not include credentials.")

        host = (parts.hostname or "").lower()
        allowed_hosts = {"instagram.com", "www.instagram.com", "m.instagram.com"}
        if host not in allowed_hosts:
            raise ValueError("URL must be an instagram.com post or reel link.")

        path_parts = [p for p in parts.path.split("/") if p]
        if len(path_parts) != 2 or path_parts[0] not in {"p", "reel"}:
            raise ValueError("Use a direct Instagram /p/ or /reel/ URL.")

        slug = path_parts[1]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
            raise ValueError("Invalid Instagram post URL.")

        return f"https://www.instagram.com/{path_parts[0]}/{slug}"

    @staticmethod
    def add_instagram_post(url):
        """Add an Instagram post URL. Max 12 posts."""
        import json
        posts = Settings.get_instagram_posts()
        url = Settings._normalize_instagram_post_url(url)
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
