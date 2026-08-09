"""Service for orchestrating document processing and OCR."""

from typing import Tuple
from flask import current_app
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository
from app.services.ocr_service import OCRService

class DocumentProcessingService:
    """Service handling the business logic of processing documents via OCR."""

    def __init__(
        self, 
        document_repo: DocumentRepository, 
        analysis_repo: DocumentAnalysisRepository,
        ocr_service: OCRService
    ):
        self.document_repo = document_repo
        self.analysis_repo = analysis_repo
        self.ocr_service = ocr_service

    def process_document(self, document_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Process a document by extracting text using OCR.
        
        Args:
            document_id: ID of the document to process.
            user_id: ID of the user requesting processing (for authorization).
            
        Returns:
            Tuple of (success_boolean, message)
        """
        # 1 & 2. Verify ownership and document exists
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document:
            return False, "Document not found or access denied."
            
        # 3. Verify physical file exists
        import os
        if not os.path.exists(document.file_path):
            self._mark_failed(document, "Physical file is missing from storage.")
            return False, "Physical file is missing."

        # 4. Call OCR Service
        result = self.ocr_service.extract_text(document.file_path, document.file_type)
        
        if not result["success"]:
            self._mark_failed(document, result["error"])
            return False, result["error"]
            
        # 5 & 6 & 7 & 8. Save extracted text and update status
        try:
            # Check if analysis record already exists (retry scenario)
            analysis = self.analysis_repo.get_by_document_id(document.id)
            
            if analysis:
                analysis.raw_text = result["text"]
            else:
                analysis = DocumentAnalysis(
                    document_id=document.id,
                    raw_text=result["text"]
                )
                self.analysis_repo.add(analysis, commit=False)
                
            document.status = "processed"
            document.error_message = None
            
            # Commit both changes atomically
            self.document_repo.commit()
            
            return True, "Document processed successfully."
            
        except Exception as e:
            self.document_repo.rollback()
            current_app.logger.error(f"Database error during document processing: {e}")
            self._mark_failed(document, "A database error occurred while saving analysis.")
            return False, "Database error during processing."

    def _mark_failed(self, document: Document, error_message: str) -> None:
        """Helper to safely mark a document as failed."""
        try:
            document.status = "failed"
            document.error_message = error_message
            self.document_repo.commit()
        except Exception as e:
            self.document_repo.rollback()
            current_app.logger.error(f"Failed to update document status to failed: {e}")
