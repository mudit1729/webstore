from datetime import datetime, timezone
from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    dress_id = db.Column(db.String(10), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    categories = db.Column(db.JSON, default=list)  # ["saree", "silk"]
    tags = db.Column(db.JSON, default=list)  # ["wedding", "red"]
    price_inr = db.Column(db.Integer, nullable=False)  # in paise
    status = db.Column(
        db.String(20), nullable=False, default="DRAFT", index=True
    )
    telegram_chat_id = db.Column(db.BigInteger)
    telegram_message_id = db.Column(db.Integer)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    images = db.relationship(
        "Image", backref="product", lazy="dynamic", cascade="all, delete-orphan"
    )
    variants = db.relationship(
        "VariantOption",
        backref="product",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="VariantOption.sort_order",
    )

    VALID_STATUSES = {"DRAFT", "PUBLISHED", "HIDDEN", "SOLD_OUT"}

    @property
    def price_inr_display(self):
        """Price in rupees as a float for display."""
        return self.price_inr / 100

    def price_usd_display(self, fx_rate):
        """Approximate USD price, rounded to whole dollars."""
        if not fx_rate or fx_rate == 0:
            return 0
        return round(self.price_inr_display / fx_rate)

    @property
    def is_visible(self):
        return self.status == "PUBLISHED"

    @property
    def original_image(self):
        return self.images.filter_by(type="ORIGINAL", status="READY").first()

    @property
    def ai_image(self):
        return (
            self.images.filter_by(type="AI_GENERATED", status="READY")
            .order_by(db.desc("version"))
            .first()
        )

    def __repr__(self):
        return f"<Product {self.dress_id}: {self.title}>"
