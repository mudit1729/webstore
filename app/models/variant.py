from app.extensions import db


class VariantOption(db.Model):
    __tablename__ = "variant_options"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = db.Column(db.String(50), nullable=False)  # "Size", "Color"
    value = db.Column(db.String(100), nullable=False)  # "Free Size"
    sort_order = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint("product_id", "type", "value", name="uq_variant"),
    )

    def __repr__(self):
        return f"<Variant {self.type}: {self.value}>"
