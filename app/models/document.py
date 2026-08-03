"""Document ORM Model mapping to 'documents' database table."""

from datetime import datetime
from typing import TYPE_CHECKING
from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document_analysis import DocumentAnalysis


class Document(db.Model):
    """Document entity storing uploaded business document metadata."""

    __tablename__ = "documents"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    user = db.relationship("User", back_populates="documents")
    analysis = db.relationship(
        "DocumentAnalysis",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename='{self.filename}' status='{self.status}'>"
