"""
Base classes and interfaces for vector store implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class ChunkType(str, Enum):
    """Type of document chunk for targeted retrieval."""
    
    # Structured policy chunks
    POLICY_META = "policy_meta"
    COVERAGE_INCLUSION = "coverage_inclusion"
    COVERAGE_EXCLUSION = "coverage_exclusion"
    FINANCIAL_TERMS = "financial_terms"
    CLIENT_OBLIGATION = "client_obligation"
    SERVICE_NETWORK = "service_network"
    
    # Auto-classified chunks (for reasoning loop)
    EXCLUSION = "exclusion"       # Any exclusion language
    INCLUSION = "inclusion"       # Any coverage/inclusion language
    DEFINITION = "definition"     # Policy definitions
    LIMITATION = "limitation"     # Limits, caps, conditions
    PROCEDURE = "procedure"       # Claims process, how-to
    
    # Raw/unclassified
    RAW_TEXT = "raw_text"
    GENERAL = "general"


@dataclass
class DocumentChunk:
    """
    A chunk of text from a document with metadata.
    
    Represents a semantically meaningful piece of text that can be
    embedded and searched. Includes citation information for legal defense.
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    chunk_type: ChunkType = ChunkType.GENERAL
    policy_id: Optional[str] = None
    category: Optional[str] = None  # e.g., "Engine", "Transmission"
    
    # Citation metadata (for "Air Canada defense")
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def citation(self) -> str:
        """Generate citation string for this chunk."""
        parts = []
        if self.page_number:
            parts.append(f"Page {self.page_number}")
        if self.section_title:
            parts.append(f"Section: {self.section_title}")
        if self.category:
            parts.append(f"Category: {self.category}")
        return ", ".join(parts) if parts else "Unspecified location"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "text": self.text,
            "chunk_type": self.chunk_type.value,
            "policy_id": self.policy_id,
            "category": self.category,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentChunk":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            text=data.get("text", ""),
            chunk_type=ChunkType(data.get("chunk_type", "general")),
            policy_id=data.get("policy_id"),
            category=data.get("category"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


@dataclass
class VectorSearchResult:
    """Result from a vector similarity search."""
    
    chunk: DocumentChunk
    score: float  # Similarity score (higher = more similar)
    rank: int = 0
    
    @property
    def is_relevant(self) -> bool:
        """Check if result is considered relevant (score > 0.5)."""
        return self.score > 0.5


class VectorStore(ABC):
    """
    Abstract base class for vector store implementations.
    
    Provides interface for:
    - Adding/removing document chunks
    - Similarity search
    - Filtering by metadata
    """
    
    @abstractmethod
    def add(self, chunk: DocumentChunk) -> str:
        """
        Add a document chunk to the store.
        
        Args:
            chunk: The DocumentChunk to add (must have embedding)
            
        Returns:
            The chunk ID
        """
        pass
    
    @abstractmethod
    def add_many(self, chunks: list[DocumentChunk]) -> list[str]:
        """
        Add multiple chunks to the store.
        
        Args:
            chunks: List of DocumentChunks to add
            
        Returns:
            List of chunk IDs
        """
        pass
    
    @abstractmethod
    def get(self, chunk_id: str) -> Optional[DocumentChunk]:
        """
        Get a chunk by ID.
        
        Args:
            chunk_id: The chunk ID
            
        Returns:
            The DocumentChunk if found, None otherwise
        """
        pass
    
    @abstractmethod
    def delete(self, chunk_id: str) -> bool:
        """
        Delete a chunk by ID.
        
        Args:
            chunk_id: The chunk ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        policy_id: Optional[str] = None,
        chunk_type: Optional[ChunkType] = None,
        category: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[VectorSearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: The query vector
            top_k: Number of results to return
            policy_id: Filter by policy ID
            chunk_type: Filter by chunk type
            category: Filter by category
            min_score: Minimum similarity score threshold
            
        Returns:
            List of VectorSearchResult ordered by similarity
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all chunks from the store."""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Get total number of chunks in store."""
        pass
    
    def delete_by_policy(self, policy_id: str) -> int:
        """
        Delete all chunks for a policy.
        
        Args:
            policy_id: The policy ID
            
        Returns:
            Number of chunks deleted
        """
        # Default implementation - subclasses can override for efficiency
        raise NotImplementedError("Subclass should implement delete_by_policy")

