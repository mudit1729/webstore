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

    def __repr__(self):
        return f"<Settings {self.key}={self.value}>"
