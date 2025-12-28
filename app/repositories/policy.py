"""
Policy Repository for policy data access.

Provides specialized methods for policy-related database operations.
"""

from typing import Optional, Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Policy
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[Policy]):
    """
    Repository for Policy model operations.
    
    Extends BaseRepository with policy-specific methods.
    """
    
    def __init__(self, db: Session):
        """Initialize the policy repository."""
        super().__init__(db, Policy)
    
    # =========================================================================
    # Policy-Specific Read Operations
    # =========================================================================
    
    def get_by_policy_id(self, policy_id: str) -> Optional[Policy]:
        """
        Get a policy by its external policy ID.
        
        Args:
            policy_id: External policy ID (e.g., "POL-2024-001")
            
        Returns:
            Policy if found, None otherwise
        """
        return self.db.query(Policy).filter(
            Policy.policy_id == policy_id
        ).first()
    
    def get_by_owner(
        self,
        owner_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> Sequence[Policy]:
        """
        Get all policies for a specific owner.
        
        Args:
            owner_id: User ID of the owner
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by status (optional)
            
        Returns:
            List of policies
        """
        query = self.db.query(Policy).filter(Policy.owner_id == owner_id)
        
        if status:
            query = query.filter(Policy.status == status)
        
        return query.order_by(Policy.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_active_policies(
        self,
        owner_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Policy]:
        """
        Get all active policies.
        
        Args:
            owner_id: Filter by owner (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of active policies
        """
        query = self.db.query(Policy).filter(Policy.status == "active")
        
        if owner_id:
            query = query.filter(Policy.owner_id == owner_id)
        
        return query.order_by(Policy.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_expiring_soon(
        self,
        days: int = 30,
        owner_id: Optional[str] = None,
    ) -> Sequence[Policy]:
        """
        Get policies expiring within a specified number of days.
        
        Args:
            days: Number of days to look ahead
            owner_id: Filter by owner (optional)
            
        Returns:
            List of policies expiring soon
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        
        query = self.db.query(Policy).filter(
            Policy.status == "active",
            Policy.end_date <= cutoff_date,
            Policy.end_date >= datetime.utcnow(),
        )
        
        if owner_id:
            query = query.filter(Policy.owner_id == owner_id)
        
        return query.order_by(Policy.end_date).all()
    
    def policy_id_exists(self, policy_id: str) -> bool:
        """
        Check if a policy ID already exists.
        
        Args:
            policy_id: External policy ID to check
            
        Returns:
            True if exists, False otherwise
        """
        return self.db.query(
            self.db.query(Policy).filter(Policy.policy_id == policy_id).exists()
        ).scalar()
    
    def count_by_owner(self, owner_id: str) -> int:
        """
        Count policies for a specific owner.
        
        Args:
            owner_id: User ID of the owner
            
        Returns:
            Number of policies
        """
        from sqlalchemy import func
        return self.db.query(func.count(Policy.id)).filter(
            Policy.owner_id == owner_id
        ).scalar() or 0
    
    def count_by_status(self, status: str) -> int:
        """
        Count policies by status.
        
        Args:
            status: Policy status
            
        Returns:
            Number of policies with that status
        """
        from sqlalchemy import func
        return self.db.query(func.count(Policy.id)).filter(
            Policy.status == status
        ).scalar() or 0
    
    # =========================================================================
    # Policy-Specific Create/Update Operations
    # =========================================================================
    
    def create_policy(
        self,
        policy_id: str,
        provider_name: str,
        policy_type: str,
        policy_data: dict,
        owner_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Policy:
        """
        Create a new policy.
        
        Args:
            policy_id: External policy ID
            provider_name: Insurance provider name
            policy_type: Type of policy
            policy_data: Full policy document as JSON
            owner_id: User ID of the owner (optional)
            start_date: Policy start date
            end_date: Policy end date
            
        Returns:
            Created policy instance
            
        Raises:
            ValueError: If policy_id already exists
        """
        if self.policy_id_exists(policy_id):
            raise ValueError(f"Policy ID '{policy_id}' already exists")
        
        return self.create(
            policy_id=policy_id,
            provider_name=provider_name,
            policy_type=policy_type,
            policy_data=policy_data,
            owner_id=owner_id,
            start_date=start_date,
            end_date=end_date,
            status="active",
            created_at=datetime.utcnow(),
        )
    
    def update_status(self, id: str, status: str) -> Optional[Policy]:
        """
        Update policy status.
        
        Args:
            id: Policy internal ID
            status: New status
            
        Returns:
            Updated policy if found, None otherwise
        """
        return self.update(id, status=status)
    
    def update_policy_data(self, id: str, policy_data: dict) -> Optional[Policy]:
        """
        Update policy document data.
        
        Args:
            id: Policy internal ID
            policy_data: New policy document data
            
        Returns:
            Updated policy if found, None otherwise
        """
        return self.update(id, policy_data=policy_data)
    
    def transfer_ownership(self, id: str, new_owner_id: str) -> Optional[Policy]:
        """
        Transfer policy ownership to another user.
        
        Args:
            id: Policy internal ID
            new_owner_id: New owner's user ID
            
        Returns:
            Updated policy if found, None otherwise
        """
        return self.update(id, owner_id=new_owner_id)
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def delete_by_owner(self, owner_id: str) -> int:
        """
        Delete all policies for a specific owner.
        
        Args:
            owner_id: User ID of the owner
            
        Returns:
            Number of policies deleted
        """
        result = self.db.query(Policy).filter(
            Policy.owner_id == owner_id
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return result
    
    def expire_old_policies(self) -> int:
        """
        Mark policies past their end date as expired.
        
        Returns:
            Number of policies expired
        """
        result = self.db.query(Policy).filter(
            Policy.status == "active",
            Policy.end_date < datetime.utcnow(),
        ).update(
            {"status": "expired", "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
        
        self.db.commit()
        return result

