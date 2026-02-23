from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.BigInteger, nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload = db.Column(db.JSON)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    ACTIONS = {
        "CREATE_DRAFT",
        "PUBLISH",
        "PUBLISH_ORIGINAL_ONLY",
        "REGENERATE_AI",
        "DISCARD",
        "MARK_SOLD_OUT",
        "HIDE",
        "UNHIDE",
        "EDIT_PRICE",
        "EDIT_METADATA",
        "SET_USD_RATE",
        "SET_WHATSAPP",
    }

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.admin_id}>"
