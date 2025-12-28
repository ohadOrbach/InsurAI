"""
Base Repository with generic CRUD operations.

Provides a reusable base class for all repositories with common database operations.
Uses Python generics for type safety.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Type, Optional, Sequence
from datetime import datetime

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from app.db.base import Base


# Type variable for the model class
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType], ABC):
    """
    Generic base repository providing CRUD operations.
    
    This abstract class provides common database operations that can be
    inherited by specific repositories.
    
    Type Parameters:
        ModelType: The SQLAlchemy model class this repository manages
    """
    
    def __init__(self, db: Session, model: Type[ModelType]):
        """
        Initialize the repository.
        
        Args:
            db: SQLAlchemy database session
            model: The model class this repository manages
        """
        self.db = db
        self.model = model
    
    # =========================================================================
    # Create Operations
    # =========================================================================
    
    def create(self, **kwargs) -> ModelType:
        """
        Create a new record.
        
        Args:
            **kwargs: Field values for the new record
            
        Returns:
            The created model instance
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def create_many(self, items: list[dict]) -> list[ModelType]:
        """
        Create multiple records.
        
        Args:
            items: List of dictionaries with field values
            
        Returns:
            List of created model instances
        """
        instances = [self.model(**item) for item in items]
        self.db.add_all(instances)
        self.db.commit()
        for instance in instances:
            self.db.refresh(instance)
        return instances
    
    # =========================================================================
    # Read Operations
    # =========================================================================
    
    def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        Get a record by its primary key.
        
        Args:
            id: The primary key value
            
        Returns:
            The model instance if found, None otherwise
        """
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> Sequence[ModelType]:
        """
        Get all records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field name to order by
            descending: Whether to sort in descending order
            
        Returns:
            List of model instances
        """
        query = self.db.query(self.model)
        
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            query = query.order_by(order_field.desc() if descending else order_field)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_field(
        self,
        field_name: str,
        value,
        first_only: bool = True,
    ) -> Optional[ModelType] | Sequence[ModelType]:
        """
        Get record(s) by a specific field value.
        
        Args:
            field_name: Name of the field to filter by
            value: Value to match
            first_only: If True, return only the first match
            
        Returns:
            Single model instance or list of instances
        """
        if not hasattr(self.model, field_name):
            raise ValueError(f"Model {self.model.__name__} has no field '{field_name}'")
        
        query = self.db.query(self.model).filter(
            getattr(self.model, field_name) == value
        )
        
        return query.first() if first_only else query.all()
    
    def exists(self, id: str) -> bool:
        """
        Check if a record exists by ID.
        
        Args:
            id: The primary key value
            
        Returns:
            True if record exists, False otherwise
        """
        return self.db.query(
            self.db.query(self.model).filter(self.model.id == id).exists()
        ).scalar()
    
    def count(self) -> int:
        """
        Count total records.
        
        Returns:
            Total number of records
        """
        return self.db.query(func.count(self.model.id)).scalar() or 0
    
    # =========================================================================
    # Update Operations
    # =========================================================================
    
    def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """
        Update a record by ID.
        
        Args:
            id: The primary key value
            **kwargs: Field values to update
            
        Returns:
            The updated model instance if found, None otherwise
        """
        instance = self.get_by_id(id)
        if not instance:
            return None
        
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        # Update timestamp if model has it
        if hasattr(instance, 'updated_at'):
            instance.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def update_many(self, ids: list[str], **kwargs) -> int:
        """
        Update multiple records by IDs.
        
        Args:
            ids: List of primary key values
            **kwargs: Field values to update
            
        Returns:
            Number of records updated
        """
        if hasattr(self.model, 'updated_at'):
            kwargs['updated_at'] = datetime.utcnow()
        
        result = self.db.query(self.model).filter(
            self.model.id.in_(ids)
        ).update(kwargs, synchronize_session=False)
        
        self.db.commit()
        return result
    
    # =========================================================================
    # Delete Operations
    # =========================================================================
    
    def delete(self, id: str) -> bool:
        """
        Delete a record by ID.
        
        Args:
            id: The primary key value
            
        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return False
        
        self.db.delete(instance)
        self.db.commit()
        return True
    
    def delete_many(self, ids: list[str]) -> int:
        """
        Delete multiple records by IDs.
        
        Args:
            ids: List of primary key values
            
        Returns:
            Number of records deleted
        """
        result = self.db.query(self.model).filter(
            self.model.id.in_(ids)
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return result
    
    # =========================================================================
    # Transaction Management
    # =========================================================================
    
    def flush(self) -> None:
        """Flush pending changes to the database."""
        self.db.flush()
    
    def commit(self) -> None:
        """Commit the current transaction."""
        self.db.commit()
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.db.rollback()
    
    def refresh(self, instance: ModelType) -> None:
        """Refresh an instance from the database."""
        self.db.refresh(instance)

