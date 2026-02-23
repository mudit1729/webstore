from datetime import datetime, timezone
from app.extensions import db


class Image(db.Model):
    __tablename__ = "images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = db.Column(db.String(20), nullable=False)  # ORIGINAL, AI_GENERATED
    version = db.Column(db.Integer, nullable=False, default=1)
    storage_key = db.Column(db.String(512), nullable=False, default="")
    url = db.Column(db.String(1024))
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    image_data = db.Column(db.LargeBinary)  # JPEG bytes stored in Postgres
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("product_id", "type", "version", name="uq_image_version"),
    )

    TYPES = {"ORIGINAL", "AI_GENERATED"}
    STATUSES = {"PENDING", "READY", "FAILED"}

    def __repr__(self):
        return f"<Image {self.type} v{self.version} [{self.status}]>"
