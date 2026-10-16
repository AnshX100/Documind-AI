"""UserRepository module for User entity persistence operations."""

from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository encapsulating specialized user queries."""

    def __init__(self) -> None:
        super().__init__(User)

    def find_by_username(self, username: str) -> User | None:
        """Find user by unique username.

        Args:
            username (str): Candidate username string.

        Returns:
            User | None: User entity if found.
        """
        return User.query.filter_by(username=username).first()

    def find_by_email(self, email: str) -> User | None:
        """Find user by unique email address.

        Args:
            email (str): Candidate email string.

        Returns:
            User | None: User entity if found.
        """
        return User.query.filter_by(email=email.lower().strip()).first()

    def find_by_google_sub(self, google_sub: str) -> User | None:
        """Find user by unique Google subject identifier (sub).

        Args:
            google_sub (str): Candidate Google sub string.

        Returns:
            User | None: User entity if found.
        """
        if not google_sub:
            return None
        return User.query.filter_by(google_sub=google_sub.strip()).first()


    def create(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = "user"
    ) -> User:
        """Create, hash password, and persist a new User entity.

        Args:
            username (str): Desired unique username.
            email (str): Valid email address.
            password (str): Plaintext password to hash.
            full_name (str | None): Optional user display name.
            role (str): User role (default 'user').

        Returns:
            User: Newly created and committed user instance.
        """
        user = User(
            username=username.strip(),
            email=email.lower().strip(),
            full_name=full_name.strip() if full_name else None,
            role=role
        )
        user.set_password(password)
        return self.add(user, commit=True)
