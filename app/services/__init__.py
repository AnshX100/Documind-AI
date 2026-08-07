"""Services package for DocuMind AI business logic."""

from flask import current_app
from werkzeug.local import LocalProxy

from app.services.auth_service import AuthService
from app.services.storage_service import StorageService
from app.services.document_service import DocumentService

from app.repositories.user_repository import UserRepository
from app.repositories.document_repository import DocumentRepository

# Repositories
user_repository = UserRepository()
document_repository = DocumentRepository()

# Services
auth_service = AuthService(user_repo=user_repository)

# Storage service needs app config, so we use a LocalProxy to initialize it lazily when requested
def _get_storage_service():
    return StorageService(
        upload_folder=current_app.config['UPLOAD_FOLDER'],
        max_content_length=current_app.config['MAX_CONTENT_LENGTH'],
        allowed_extensions=current_app.config['ALLOWED_EXTENSIONS']
    )

storage_service = LocalProxy(_get_storage_service)
document_service = DocumentService(document_repo=document_repository, storage_service=storage_service)

__all__ = ["auth_service", "storage_service", "document_service"]
