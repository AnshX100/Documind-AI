"""Authentication service for handling business logic related to user sessions and registration."""

from typing import Tuple, Dict, Any
from app.repositories.user_repository import UserRepository
from flask_login import login_user, logout_user, current_user
from app.models.user import User

class AuthService:
    """Service encapsulating authentication and registration logic."""

    def __init__(self, user_repo: UserRepository) -> None:
        """Initialize with user repository dependency."""
        self.user_repo = user_repo

    def register_user(self, username: str, email: str, password: str, full_name: str | None = None) -> Tuple[bool, str, User | None]:
        """Handles user registration logic.

        Args:
            username (str): Desired username.
            email (str): User email.
            password (str): Plain text password.
            full_name (str | None): Optional full name.

        Returns:
            Tuple[bool, str, User | None]: Success flag, message, and created user (if successful).
        """
        # Check if username exists
        if self.user_repo.find_by_username(username):
            return False, "Username is already taken.", None

        # Check if email exists
        if self.user_repo.find_by_email(email):
            return False, "Email is already registered.", None

        try:
            user = self.user_repo.create(
                username=username,
                email=email,
                password=password,
                full_name=full_name
            )
            return True, "Registration successful! You can now log in.", user
        except Exception as e:
            # Proper error handling and logging should go here
            return False, f"An error occurred during registration: {str(e)}", None

    def login_user(self, email: str, password: str, remember: bool = False) -> Tuple[bool, str]:
        """Handles user login logic.

        Args:
            email (str): User email address.
            password (str): Plain text password.
            remember (bool): Whether to remember the session.

        Returns:
            Tuple[bool, str]: Success flag and message.
        """
        user = self.user_repo.find_by_email(email)
        
        if not user:
            return False, "Invalid email address or password."

        if not user.is_active:
            return False, "This account has been deactivated. Please contact support."

        if user.check_password(password):
            login_user(user, remember=remember)
            return True, f"Welcome back, {user.username}!"
            
        return False, "Invalid email address or password."

    def logout_user(self) -> None:
        """Logs out the current user."""
        if current_user.is_authenticated:
            logout_user()
