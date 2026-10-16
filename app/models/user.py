"""User ORM Model mapping to 'users' database table."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.report import Report
    from app.models.chat_history import ChatHistory


class User(UserMixin, db.Model):
    """User entity representing authenticated system accounts."""

    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    google_sub = db.Column(db.String(255), unique=True, nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    documents = db.relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    reports = db.relationship(
        "Report",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    chat_histories = db.relationship(
        "ChatHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def set_password(self, password: str) -> None:
        """Hashes and sets the user's password using PBKDF2:SHA256.

        Args:
            password (str): Plain text user password.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies candidate password against stored hash.

        Args:
            password (str): Plain text password candidate.

        Returns:
            bool: True if password matches, False otherwise.
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}'>"
