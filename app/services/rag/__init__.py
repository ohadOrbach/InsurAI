"""
Enhanced RAG (Retrieval-Augmented Generation) module.

Provides advanced retrieval capabilities:
- Smart chunking with overlap
- Hybrid search (keyword + semantic)
- Query reranking
"""

from app.services.rag.chunker import (
    SmartChunker,
    ChunkingStrategy,
    Chunk,
)
from app.services.rag.hybrid_search import (
    HybridSearchEngine,
    SearchResult,
    SearchMode,
)
from app.services.rag.reranker import (
    Reranker,
    MockReranker,
    RerankedResult,
)

__all__ = [
    "SmartChunker",
    "ChunkingStrategy",
    "Chunk",
    "HybridSearchEngine",
    "SearchResult",
    "SearchMode",
    "Reranker",
    "MockReranker",
    "RerankedResult",
]

