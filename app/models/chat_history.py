"""ChatHistory ORM Model mapping to 'chat_history' database table."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document


class ChatHistory(db.Model):
    """ChatHistory entity storing user interaction history with AI Assistant."""

    __tablename__ = "chat_history"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = db.Column(db.String(20), nullable=False) # 'user' or 'assistant'
    conversation_id = db.Column(db.String(36), nullable=True, index=True)
    message = db.Column(db.Text, nullable=False)
    referenced_doc_id = db.Column(
        db.BigInteger,
        db.ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    # Relationships
    user = db.relationship("User", back_populates="chat_histories")
    referenced_document = db.relationship("Document")

    def __repr__(self) -> str:
        return f"<ChatHistory id={self.id} user_id={self.user_id} role='{self.role}'>"
