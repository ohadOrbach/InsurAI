"""
In-memory vector store implementation.

Provides a lightweight vector store for development and testing.
Uses numpy for efficient similarity calculations.
"""

import logging
from typing import Optional

import numpy as np

from .base import ChunkType, DocumentChunk, VectorSearchResult, VectorStore

logger = logging.getLogger(__name__)


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store using numpy for similarity search.
    
    Features:
    - Fast similarity search using numpy operations
    - Filtering by metadata
    - No external dependencies
    
    Suitable for:
    - Development and testing
    - Small to medium datasets (<100k chunks)
    - Single-instance deployments
    
    For production with large datasets, use ChromaDB, Pinecone, or Milvus.
    """
    
    def __init__(self):
        """Initialize empty vector store."""
        self._chunks: dict[str, DocumentChunk] = {}
        self._embeddings: dict[str, np.ndarray] = {}
        self._policy_index: dict[str, set[str]] = {}  # policy_id -> chunk_ids
    
    def add(self, chunk: DocumentChunk) -> str:
        """Add a single chunk to the store."""
        if chunk.embedding is None:
            raise ValueError("Chunk must have an embedding")
        
        # Store chunk and embedding
        self._chunks[chunk.id] = chunk
        self._embeddings[chunk.id] = np.array(chunk.embedding, dtype=np.float32)
        
        # Update policy index
        if chunk.policy_id:
            if chunk.policy_id not in self._policy_index:
                self._policy_index[chunk.policy_id] = set()
            self._policy_index[chunk.policy_id].add(chunk.id)
        
        return chunk.id
    
    def add_many(self, chunks: list[DocumentChunk]) -> list[str]:
        """Add multiple chunks to the store."""
        ids = []
        for chunk in chunks:
            chunk_id = self.add(chunk)
            ids.append(chunk_id)
        return ids
    
    def get(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Get a chunk by ID."""
        return self._chunks.get(chunk_id)
    
    def delete(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        if chunk_id not in self._chunks:
            return False
        
        chunk = self._chunks[chunk_id]
        
        # Remove from policy index
        if chunk.policy_id and chunk.policy_id in self._policy_index:
            self._policy_index[chunk.policy_id].discard(chunk_id)
        
        # Remove chunk and embedding
        del self._chunks[chunk_id]
        del self._embeddings[chunk_id]
        
        return True
    
    def delete_by_policy(self, policy_id: str) -> int:
        """Delete all chunks for a policy."""
        if policy_id not in self._policy_index:
            return 0
        
        chunk_ids = list(self._policy_index[policy_id])
        count = 0
        
        for chunk_id in chunk_ids:
            if self.delete(chunk_id):
                count += 1
        
        # Clean up empty policy entry
        if policy_id in self._policy_index:
            del self._policy_index[policy_id]
        
        return count
    
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
        Search for similar chunks using cosine similarity.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            policy_id: Filter by policy ID
            chunk_type: Filter by chunk type
            category: Filter by category
            min_score: Minimum similarity threshold
            
        Returns:
            List of VectorSearchResult sorted by similarity (descending)
        """
        if not self._chunks:
            return []
        
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        
        if query_norm == 0:
            return []
        
        query_vec = query_vec / query_norm
        
        # Get candidate chunk IDs based on filters
        if policy_id and policy_id in self._policy_index:
            candidate_ids = self._policy_index[policy_id]
        else:
            candidate_ids = set(self._chunks.keys())
        
        # Calculate similarities
        results = []
        
        for chunk_id in candidate_ids:
            chunk = self._chunks[chunk_id]
            
            # Apply filters
            if chunk_type and chunk.chunk_type != chunk_type:
                continue
            if category and chunk.category != category:
                continue
            
            # Calculate cosine similarity
            chunk_vec = self._embeddings[chunk_id]
            chunk_norm = np.linalg.norm(chunk_vec)
            
            if chunk_norm == 0:
                continue
            
            similarity = np.dot(query_vec, chunk_vec / chunk_norm)
            
            if similarity >= min_score:
                results.append((chunk, float(similarity)))
        
        # Sort by similarity (descending) and take top_k
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:top_k]
        
        # Convert to VectorSearchResult
        return [
            VectorSearchResult(chunk=chunk, score=score, rank=i + 1)
            for i, (chunk, score) in enumerate(results)
        ]
    
    def clear(self) -> None:
        """Clear all data from the store."""
        self._chunks.clear()
        self._embeddings.clear()
        self._policy_index.clear()
    
    def count(self) -> int:
        """Get total number of chunks."""
        return len(self._chunks)
    
    def count_by_policy(self, policy_id: str) -> int:
        """Get number of chunks for a specific policy."""
        if policy_id not in self._policy_index:
            return 0
        return len(self._policy_index[policy_id])
    
    def get_all_policy_ids(self) -> list[str]:
        """Get all policy IDs in the store."""
        return list(self._policy_index.keys())
    
    def get_chunks_by_policy(self, policy_id: str) -> list[DocumentChunk]:
        """Get all chunks for a policy."""
        if policy_id not in self._policy_index:
            return []
        
        return [
            self._chunks[chunk_id]
            for chunk_id in self._policy_index[policy_id]
            if chunk_id in self._chunks
        ]
    
    def get_stats(self) -> dict:
        """Get store statistics."""
        chunk_types = {}
        categories = {}
        
        for chunk in self._chunks.values():
            # Count by type
            type_name = chunk.chunk_type.value
            chunk_types[type_name] = chunk_types.get(type_name, 0) + 1
            
            # Count by category
            if chunk.category:
                categories[chunk.category] = categories.get(chunk.category, 0) + 1
        
        return {
            "total_chunks": len(self._chunks),
            "total_policies": len(self._policy_index),
            "chunks_by_type": chunk_types,
            "chunks_by_category": categories,
        }

