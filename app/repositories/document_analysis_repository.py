"""DocumentAnalysis repository for database operations."""

from typing import Optional
from app.repositories.base_repository import BaseRepository
from app.models.document_analysis import DocumentAnalysis
from app.extensions import db

class DocumentAnalysisRepository(BaseRepository[DocumentAnalysis]):
    """Repository handling document analysis data access."""

    def __init__(self) -> None:
        super().__init__(DocumentAnalysis)

    def get_by_document_id(self, document_id: int) -> Optional[DocumentAnalysis]:
        """Fetch the analysis record for a given document."""
        return DocumentAnalysis.query.filter_by(document_id=document_id).first()
