"""DocumentAnalysis ORM Model mapping to 'document_analysis' database table."""

from datetime import datetime, date, timezone
from typing import TYPE_CHECKING
from app.extensions import db

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentAnalysis(db.Model):
    """DocumentAnalysis entity storing OCR & AI extracted financial metrics."""

    __tablename__ = "document_analysis"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    document_id = db.Column(
        db.BigInteger,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    from sqlalchemy.dialects.mysql import LONGTEXT
    raw_text = db.Column(db.Text().with_variant(LONGTEXT, "mysql"), nullable=True)
    vendor_name = db.Column(db.String(200), nullable=True, index=True)
    invoice_number = db.Column(db.String(100), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True, index=True)
    total_amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0.00,
        index=True
    )
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    subtotal_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    category = db.Column(
        db.String(100),
        nullable=False,
        default="General",
        index=True
    )
    payment_method = db.Column(db.String(50), nullable=True, default="Unknown")
    ai_summary = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document = db.relationship("Document", back_populates="analysis")

    def __repr__(self) -> str:
        return (
            f"<DocumentAnalysis id={self.id} doc_id={self.document_id} "
            f"vendor='{self.vendor_name}' amount={self.total_amount}>"
        )
