from flask import current_app
from werkzeug.local import LocalProxy

from app.services.auth_service import AuthService
from app.services.storage_service import StorageService
from app.services.document_service import DocumentService
from app.services.ocr_service import OCRService
from app.services.document_processing_service import DocumentProcessingService

from app.repositories.user_repository import UserRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_analysis_repository import DocumentAnalysisRepository

# Repositories
user_repository = UserRepository()
document_repository = DocumentRepository()
document_analysis_repository = DocumentAnalysisRepository()

# Services
auth_service = AuthService(user_repo=user_repository)

# LocalProxy for StorageService (needs app config)
def _get_storage_service():
    return StorageService(
        upload_folder=current_app.config['UPLOAD_FOLDER'],
        max_content_length=current_app.config['MAX_CONTENT_LENGTH'],
        allowed_extensions=current_app.config['ALLOWED_EXTENSIONS']
    )

storage_service = LocalProxy(_get_storage_service)
document_service = DocumentService(document_repo=document_repository, storage_service=storage_service)

# LocalProxy for OCRService (needs app config for tesseract)
def _get_ocr_service():
    return OCRService(
        tesseract_cmd=current_app.config.get('TESSERACT_CMD'),
        language=current_app.config.get('OCR_LANGUAGE', 'eng')
    )

ocr_service = LocalProxy(_get_ocr_service)
document_processing_service = DocumentProcessingService(
    document_repo=document_repository,
    analysis_repo=document_analysis_repository,
    ocr_service=ocr_service
)

__all__ = [
    "auth_service", 
    "storage_service", 
    "document_service", 
    "ocr_service", 
    "document_processing_service",
    "user_repository",
    "document_repository",
    "document_analysis_repository"
]
