"""Document service for orchestrating document upload, deletion, and retrieval."""
import os
from typing import Tuple, Optional
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.storage_service import StorageService

class DocumentService:
    """Service handling business logic for documents."""

    def __init__(self, document_repo: DocumentRepository, storage_service: StorageService):
        """Initialize with repository and storage service dependencies."""
        self.document_repo = document_repo
        self.storage_service = storage_service

    def upload_document(self, user_id: int, file: FileStorage) -> Tuple[bool, str, Optional[Document]]:
        """Coordinates the document upload and database entry process.
        
        Args:
            user_id: The ID of the authenticated user.
            file: The uploaded file from the form.
            
        Returns:
            Tuple of (success_boolean, message, optional_document)
        """
        if not file or not file.filename:
            return False, "No selected file.", None
            
        original_filename = secure_filename(file.filename)
        
        try:
            # 1. Save physical file
            physical_path, file_type, file_size = self.storage_service.save_file(file, user_id)
            
            try:
                # 2. Create database record
                document = Document(
                    user_id=user_id,
                    filename=os.path.basename(physical_path),
                    original_filename=original_filename,
                    file_path=physical_path,
                    file_type=file_type,
                    file_size=file_size,
                    status="pending"
                )
                
                self.document_repo.add(document, commit=True)
                return True, "Document uploaded successfully.", document
                
            except Exception as db_err:
                # Database insertion failed, rollback physical file
                current_app.logger.error(f"Database error during upload: {db_err}")
                self.storage_service.delete_file(physical_path)
                return False, "Database error during upload. File was not saved.", None
                
        except ValueError as val_err:
            return False, str(val_err), None
        except Exception as e:
            current_app.logger.error(f"Storage error during upload: {e}")
            return False, "An error occurred while saving the file.", None

    def delete_document(self, document_id: int, user_id: int) -> Tuple[bool, str]:
        """Deletes a document securely.
        
        Args:
            document_id: The document to delete.
            user_id: The authenticated user's ID (to verify ownership).
            
        Returns:
            Tuple of (success_boolean, message)
        """
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document:
            return False, "Document not found or access denied."
            
        # Delete physical file
        self.storage_service.delete_file(document.file_path)
        
        # Delete database record
        try:
            self.document_repo.delete(document, commit=True)
            return True, "Document deleted successfully."
        except Exception as e:
            current_app.logger.error(f"Error deleting document record: {e}")
            return False, "An error occurred while deleting the document record."
            
    def get_document_for_download(self, document_id: int, user_id: int) -> Tuple[bool, str, Optional[Document]]:
        """Validates ownership and returns the absolute path for download.
        
        Returns:
            Tuple of (success_boolean, message_or_path, document)
        """
        document = self.document_repo.get_by_id_and_user(document_id, user_id)
        if not document:
            return False, "Document not found or access denied.", None
            
        import os
        if not os.path.exists(document.file_path):
            return False, "Physical file is missing from storage.", document
            
        return True, document.file_path, document
