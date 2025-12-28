"""
Authentication service for user management.

Handles user registration, login, and token management.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    generate_user_id,
)
from app.db.models import User
from app.schemas.user import UserCreate, UserInDB, UserResponse


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: Session):
        """
        Initialize auth service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            email: User's email address
            
        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email.lower()).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User's ID
            
        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user.
        
        Args:
            user_data: User registration data
            
        Returns:
            Created user
            
        Raises:
            ValueError: If email already exists
        """
        # Check if email already exists
        if self.get_user_by_email(user_data.email):
            raise ValueError("Email already registered")
        
        # Create user
        user = User(
            id=generate_user_id(),
            email=user_data.email.lower(),
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            User if credentials valid, None otherwise
        """
        user = self.get_user_by_email(email)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        return user
    
    def create_token_for_user(self, user: User) -> dict:
        """
        Create access token for user.
        
        Args:
            user: User to create token for
            
        Returns:
            Token response dict
        """
        from app.core.config import settings
        
        access_token = create_access_token(
            subject=user.id,
            additional_claims={
                "email": user.email,
                "is_superuser": user.is_superuser,
            }
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    
    def update_user(
        self,
        user: User,
        full_name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> User:
        """
        Update user information.
        
        Args:
            user: User to update
            full_name: New full name (optional)
            password: New password (optional)
            
        Returns:
            Updated user
        """
        if full_name is not None:
            user.full_name = full_name
        
        if password is not None:
            user.hashed_password = get_password_hash(password)
        
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def deactivate_user(self, user: User) -> User:
        """
        Deactivate a user account.
        
        Args:
            user: User to deactivate
            
        Returns:
            Updated user
        """
        user.is_active = False
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(user)
        
        return user

