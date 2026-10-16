"""Report ORM Model mapping to 'reports' database table."""

from datetime import datetime, date, timezone
from typing import TYPE_CHECKING
from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class Report(db.Model):
    """Report entity storing generated financial analysis exports."""

    __tablename__ = "reports"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    report_name = db.Column(db.String(200), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    total_expenses = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    total_documents = db.Column(db.Integer, nullable=False, default=0)
    file_path = db.Column(db.String(500), nullable=True)
    format = db.Column(db.String(10), nullable=False, default="pdf")
    status = db.Column(db.String(20), nullable=False, default="completed")
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = db.relationship("User", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report id={self.id} name='{self.report_name}' status='{self.status}' format='{self.format}'>"

