"""Base repository providing generic CRUD database access methods."""

from typing import Generic, TypeVar, Type, Sequence, Any
from app.extensions import db

T = TypeVar("T", bound=db.Model)


class BaseRepository(Generic[T]):
    """Generic repository encapsulating database queries and mutations."""

    def __init__(self, model: Type[T]) -> None:
        """Initialize repository with target entity model.

        Args:
            model (Type[T]): SQLAlchemy entity class.
        """
        self.model = model

    def get_by_id(self, entity_id: int) -> T | None:
        """Retrieve single entity by primary key ID.

        Args:
            entity_id (int): Entity primary key.

        Returns:
            T | None: Entity instance if found, None otherwise.
        """
        return db.session.get(self.model, entity_id)

    def get_all(self) -> Sequence[T]:
        """Fetch all entity records.

        Returns:
            Sequence[T]: List of entities.
        """
        return db.session.query(self.model).all()

    def add(self, entity: T, commit: bool = False) -> T:
        """Add entity to session.

        Args:
            entity (T): Entity instance to add.
            commit (bool): If True, commits transaction immediately.

        Returns:
            T: Added entity.
        """
        db.session.add(entity)
        if commit:
            db.session.commit()
        return entity

    def delete(self, entity: T, commit: bool = False) -> None:
        """Remove entity from session.

        Args:
            entity (T): Entity instance to delete.
            commit (bool): If True, commits transaction immediately.
        """
        db.session.delete(entity)
        if commit:
            db.session.commit()

    def commit(self) -> None:
        """Commit current database transaction session."""
        db.session.commit()

    def rollback(self) -> None:
        """Rollback current database transaction session."""
        db.session.rollback()
