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
        """Logs out the current user and clears session state."""
        from flask import session
        
        # Invoke Flask-Login's logout_user() to pop _user_id, _fresh, _id
        # and set session["_remember"] = "clear"
        logout_user()

        # Clear application-specific authentication keys and user data,
        # but preserve '_remember' (needed by Flask-Login's after-request hook to delete the remember cookie)
        # and '_flashes' (for flash messages)
        keys_to_preserve = {'_remember', '_flashes'}
        keys_to_remove = [k for k in list(session.keys()) if k not in keys_to_preserve and not k.startswith('_csrf')]
        for k in keys_to_remove:
            session.pop(k, None)

    def handle_google_login(self, google_sub: str, email: str, name: str | None = None) -> Tuple[bool, str, User | None, str | None]:
        """Handles Google OAuth user resolution and login following strict security policy.
        
        Policy:
        - If google_sub matches existing user: authenticate user.
        - If no user by google_sub, but existing password user has matching email:
          DO NOT automatically link. Return action_required='link_required'.
        - If no existing user: create new user with role 'user' and log in.
        
        Returns:
            Tuple[bool, str, User | None, str | None]: (success, message, user_object, action_required_flag)
        """
        import secrets
        import re

        # 1. Check if user exists by google_sub
        existing_google_user = self.user_repo.find_by_google_sub(google_sub)
        if existing_google_user:
            if not existing_google_user.is_active:
                return False, "This account has been deactivated. Please contact support.", None, None
            login_user(existing_google_user)
            return True, f"Welcome back, {existing_google_user.username}!", existing_google_user, None

        # 2. Check if user exists by email (DO NOT AUTO-LINK!)
        existing_email_user = self.user_repo.find_by_email(email)
        if existing_email_user:
            return (
                False,
                "An account with this email address already exists. Please sign in using your password and connect Google from your account settings.",
                None,
                "link_required"
            )

        # 3. Create new user account with role='user'
        clean_email = email.lower().strip()
        base_username = clean_email.split('@')[0]
        base_username = re.sub(r'[^a-zA-Z0-9_]', '', base_username) or "user"
        
        username = base_username
        counter = 1
        while self.user_repo.find_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        random_password = secrets.token_urlsafe(32)

        try:
            new_user = User(
                username=username,
                email=clean_email,
                full_name=name.strip() if name else None,
                google_sub=google_sub,
                role="user"
            )
            new_user.set_password(random_password)
            user = self.user_repo.add(new_user, commit=True)
            login_user(user)
            return True, f"Welcome to DocuMind AI, {user.username}!", user, None
        except Exception as e:
            return False, f"Error creating Google authenticated user: {str(e)}", None, None

    def link_google_account(self, user_id: int, google_sub: str) -> Tuple[bool, str]:
        """Explicitly links a Google sub identifier to an authenticated user account."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return False, "User account not found."

        existing_sub = self.user_repo.find_by_google_sub(google_sub)
        if existing_sub and existing_sub.id != user.id:
            return False, "This Google account is already linked to another user account."

        try:
            user.google_sub = google_sub
            self.user_repo.commit()
            return True, "Google account connected successfully."
        except Exception as e:
            self.user_repo.rollback()
            return False, f"Failed to link Google account: {str(e)}"

