"""Document repository for database operations on documents."""

from typing import Tuple, List, Optional
from flask_sqlalchemy.pagination import Pagination
from app.repositories.base_repository import BaseRepository
from app.models.document import Document
from app.extensions import db

class DocumentRepository(BaseRepository[Document]):
    """Repository handling document data access and queries."""

    def __init__(self) -> None:
        super().__init__(Document)

    def get_by_id_and_user(self, document_id: int, user_id: int) -> Optional[Document]:
        """Fetch a document ensuring it belongs to the specified user."""
        return Document.query.filter_by(id=document_id, user_id=user_id).first()

    def get_user_documents_paginated(
        self, 
        user_id: int, 
        page: int = 1, 
        per_page: int = 10,
        search_query: str = "",
        status_filter: str = "all"
    ) -> Pagination:
        """Fetch paginated documents for a user with optional search and filter.
        
        Args:
            user_id: The ID of the owner.
            page: Current page number.
            per_page: Number of items per page.
            search_query: Optional string to match against filename.
            status_filter: Optional status to filter by ('all', 'pending', 'processed', 'failed').
            
        Returns:
            Flask-SQLAlchemy Pagination object.
        """
        query = Document.query.filter_by(user_id=user_id)
        
        if search_query:
            search_term = f"%{search_query}%"
            # Search in original filename or file type
            query = query.filter(
                (Document.original_filename.ilike(search_term)) | 
                (Document.file_type.ilike(search_term))
            )
            
        if status_filter and status_filter.lower() != "all":
            query = query.filter_by(status=status_filter.lower())
            
        # Order by newest first
        query = query.order_by(Document.created_at.desc())
        
        return query.paginate(page=page, per_page=per_page, error_out=False)

    def count_user_documents_by_status(self, user_id: int) -> dict[str, int]:
        """Get document counts for a user grouped by status.
        
        Returns a dictionary like {'total': 10, 'pending': 2, 'processed': 8, 'failed': 0}
        """
        # Execute query to count statuses
        counts = db.session.query(
            Document.status, db.func.count(Document.id)
        ).filter(Document.user_id == user_id).group_by(Document.status).all()
        
        result = {'total': 0, 'pending': 0, 'processed': 0, 'failed': 0}
        
        for status, count in counts:
            result[status] = count
            result['total'] += count
            
        return result
        
    def get_recent_user_documents(self, user_id: int, limit: int = 5) -> List[Document]:
        """Fetch the most recent documents for a user."""
        return Document.query.filter_by(user_id=user_id).order_by(Document.created_at.desc()).limit(limit).all()
