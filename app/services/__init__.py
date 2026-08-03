"""Services package for DocuMind AI business logic."""

from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository

# Instantiate singletons for service layer, injecting repositories
user_repository = UserRepository()
auth_service = AuthService(user_repo=user_repository)

__all__ = ["auth_service"]
