"""Service for orchestrating document processing and OCR."""

from typing import Tuple
from flask import current_app
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository
from app.services.ocr_service import OCRService
from app.services.ai_service import AIService

class DocumentProcessingService:
    """Service handling the business logic of processing documents via OCR and AI extraction."""

    def __init__(
        self, 
        document_repo: DocumentRepository, 
        analysis_repo: DocumentAnalysisRepository,
        ocr_service: OCRService,
        ai_service: AIService
    ):
        self.document_repo = document_repo
        self.analysis_repo = analysis_repo
        self.ocr_service = ocr_service
        self.ai_service = ai_service

    def process_document(self, document_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Process a document by extracting text using OCR, then parsing financial data.
        """
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document:
            return False, "Document not found or access denied."
            
        import os
        if not os.path.exists(document.file_path):
            self._mark_failed(document, "Physical file is missing from storage.")
            return False, "Physical file is missing."

        # 4. Call OCR Service
        result = self.ocr_service.extract_text(document.file_path, document.file_type)
        
        if not result["success"]:
            self._mark_failed(document, result["error"])
            return False, result["error"]

        # 5. Format OCR text and extract Financial Data
        raw_text = result["text"]
        from app.services.ocr_formatter_service import OCRFormatterService
        formatter = OCRFormatterService()
        formatted_text = formatter.format_text(raw_text)
        
        financial_data = self.ai_service.extract_financial_data(formatted_text)
            
        # 6. Save extracted text and structured data
        try:
            analysis = self.analysis_repo.get_by_document_id(document.id)
            
            if analysis:
                analysis.raw_text = raw_text
                self._update_analysis_fields(analysis, financial_data)
            else:
                analysis = DocumentAnalysis(
                    document_id=document.id,
                    raw_text=raw_text
                )
                self._update_analysis_fields(analysis, financial_data)
                self.analysis_repo.add(analysis, commit=False)
                
            document.status = "processed"
            document.error_message = None
            
            self.document_repo.commit()
            return True, "Document processed and analyzed successfully."
            
        except Exception as e:
            self.document_repo.rollback()
            current_app.logger.error(f"Database error during document processing: {e}")
            self._mark_failed(document, "A database error occurred while saving analysis.")
            return False, "Database error during processing."

    def reanalyze_document(self, document_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Re-run financial extraction using existing OCR text.
        """
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document:
            return False, "Document not found or access denied."
            
        analysis = self.analysis_repo.get_by_document_id(document.id)
        if not analysis or not analysis.raw_text:
            return False, "No OCR text found. Please process the document first."
            
        try:
            from app.services.ocr_formatter_service import OCRFormatterService
            formatter = OCRFormatterService()
            formatted_text = formatter.format_text(analysis.raw_text)
            
            financial_data = self.ai_service.extract_financial_data(formatted_text)
            self._update_analysis_fields(analysis, financial_data)
            self.document_repo.commit()
            return True, "Financial analysis updated successfully."
        except Exception as e:
            self.document_repo.rollback()
            current_app.logger.error(f"Database error during re-analysis: {e}")
            return False, "Database error during re-analysis."

    def _update_analysis_fields(self, analysis: DocumentAnalysis, data: dict) -> None:
        """Helper to safely map structured dict to model fields."""
        analysis.vendor_name = data.get("vendor_name")
        analysis.invoice_number = data.get("invoice_number")
        analysis.invoice_date = data.get("invoice_date")
        analysis.subtotal_amount = data.get("subtotal_amount") or 0.00
        analysis.tax_amount = data.get("tax_amount") or 0.00
        analysis.total_amount = data.get("total_amount") or 0.00
        analysis.category = data.get("category", "General")
        analysis.payment_method = data.get("payment_method", "Unknown")
        analysis.confidence_score = data.get("confidence_score", 0.0)
        analysis.ai_summary = data.get("ai_summary")

    def _mark_failed(self, document: Document, error_message: str) -> None:
        """Helper to safely mark a document as failed."""
        try:
            document.status = "failed"
            document.error_message = error_message
            self.document_repo.commit()
        except Exception as e:
            self.document_repo.rollback()
            current_app.logger.error(f"Failed to update document status to failed: {e}")
