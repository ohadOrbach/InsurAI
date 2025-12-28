"""
Vector Store module for semantic search capabilities.

Provides:
- Text embedding generation
- Vector storage and retrieval
- Semantic similarity search
"""

from .base import VectorStore, VectorSearchResult, DocumentChunk, ChunkType
from .embeddings import EmbeddingService, MockEmbeddingService
from .memory_store import InMemoryVectorStore
from .policy_vectorizer import PolicyVectorizer

__all__ = [
    "VectorStore",
    "VectorSearchResult",
    "DocumentChunk",
    "ChunkType",
    "EmbeddingService",
    "MockEmbeddingService",
    "InMemoryVectorStore",
    "PolicyVectorizer",
]

