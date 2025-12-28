"""
Hybrid Search Engine combining keyword and semantic search.

Provides better retrieval by combining:
- BM25 for keyword matching
- Vector similarity for semantic matching
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math


class SearchMode(str, Enum):
    """Search mode options."""
    KEYWORD = "keyword"  # BM25 only
    SEMANTIC = "semantic"  # Vector similarity only
    HYBRID = "hybrid"  # Combined


@dataclass
class SearchResult:
    """A search result with scores."""
    
    chunk_id: str
    text: str
    score: float  # Combined score
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "score": self.score,
            "keyword_score": self.keyword_score,
            "semantic_score": self.semantic_score,
            "metadata": self.metadata,
        }


class BM25:
    """
    BM25 (Best Matching 25) algorithm for keyword search.
    
    A probabilistic ranking function used for information retrieval.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25.
        
        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.doc_freqs = {}  # term -> document frequency
        self.idf = {}  # term -> inverse document frequency
        self.doc_term_freqs = []  # doc_idx -> {term: freq}
    
    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into terms."""
        # Simple tokenization: lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def fit(self, documents: list[str]) -> None:
        """
        Fit BM25 on a corpus of documents.
        
        Args:
            documents: List of document texts
        """
        self.corpus = documents
        self.doc_lengths = []
        self.doc_freqs = {}
        self.doc_term_freqs = []
        
        # Calculate document frequencies
        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            
            term_freqs = {}
            seen_terms = set()
            
            for token in tokens:
                term_freqs[token] = term_freqs.get(token, 0) + 1
                if token not in seen_terms:
                    self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
                    seen_terms.add(token)
            
            self.doc_term_freqs.append(term_freqs)
        
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if documents else 0
        
        # Calculate IDF for each term
        n_docs = len(documents)
        for term, df in self.doc_freqs.items():
            # IDF with smoothing
            self.idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
    
    def score(self, query: str, doc_idx: int) -> float:
        """
        Calculate BM25 score for a query against a document.
        
        Args:
            query: Search query
            doc_idx: Document index in corpus
            
        Returns:
            BM25 score
        """
        if doc_idx >= len(self.corpus):
            return 0.0
        
        query_tokens = self._tokenize(query)
        doc_term_freq = self.doc_term_freqs[doc_idx]
        doc_length = self.doc_lengths[doc_idx]
        
        score = 0.0
        
        for token in query_tokens:
            if token not in self.idf:
                continue
            
            tf = doc_term_freq.get(token, 0)
            idf = self.idf[token]
            
            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            
            score += idf * (numerator / denominator) if denominator > 0 else 0
        
        return score
    
    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """
        Search for documents matching query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (doc_idx, score) tuples, sorted by score descending
        """
        scores = []
        
        for idx in range(len(self.corpus)):
            score = self.score(query, idx)
            if score > 0:
                scores.append((idx, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class HybridSearchEngine:
    """
    Hybrid search engine combining keyword (BM25) and semantic (vector) search.
    
    Provides better retrieval for insurance documents by leveraging both
    exact keyword matching and semantic understanding.
    """
    
    def __init__(
        self,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        default_mode: SearchMode = SearchMode.HYBRID,
    ):
        """
        Initialize hybrid search engine.
        
        Args:
            keyword_weight: Weight for keyword search (0-1)
            semantic_weight: Weight for semantic search (0-1)
            default_mode: Default search mode
        """
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight
        self.default_mode = default_mode
        
        # BM25 index
        self.bm25 = BM25()
        
        # Document store
        self.documents = []  # List of {id, text, embedding, metadata}
        self.id_to_idx = {}  # chunk_id -> index
    
    def add_documents(
        self,
        documents: list[dict],
    ) -> None:
        """
        Add documents to the search index.
        
        Args:
            documents: List of dicts with 'id', 'text', 'embedding', 'metadata'
        """
        for doc in documents:
            if doc["id"] in self.id_to_idx:
                continue  # Skip duplicates
            
            idx = len(self.documents)
            self.documents.append(doc)
            self.id_to_idx[doc["id"]] = idx
        
        # Rebuild BM25 index
        texts = [d["text"] for d in self.documents]
        self.bm25.fit(texts)
    
    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the index.
        
        Args:
            doc_id: Document ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if doc_id not in self.id_to_idx:
            return False
        
        idx = self.id_to_idx[doc_id]
        del self.documents[idx]
        
        # Rebuild index mappings
        self.id_to_idx = {d["id"]: i for i, d in enumerate(self.documents)}
        
        # Rebuild BM25
        texts = [d["text"] for d in self.documents]
        self.bm25.fit(texts)
        
        return True
    
    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def search(
        self,
        query: str,
        query_embedding: Optional[list[float]] = None,
        mode: Optional[SearchMode] = None,
        top_k: int = 10,
        min_score: float = 0.0,
        policy_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query text
            query_embedding: Query embedding vector (required for semantic search)
            mode: Search mode (defaults to self.default_mode)
            top_k: Number of results to return
            min_score: Minimum score threshold
            policy_id: Filter by policy ID (optional)
            
        Returns:
            List of search results sorted by score
        """
        mode = mode or self.default_mode
        
        if not self.documents:
            return []
        
        # Filter by policy_id if specified
        doc_indices = list(range(len(self.documents)))
        if policy_id:
            doc_indices = [
                i for i, d in enumerate(self.documents)
                if d.get("metadata", {}).get("policy_id") == policy_id
            ]
        
        if not doc_indices:
            return []
        
        results = []
        
        for idx in doc_indices:
            doc = self.documents[idx]
            keyword_score = 0.0
            semantic_score = 0.0
            
            # Keyword search
            if mode in [SearchMode.KEYWORD, SearchMode.HYBRID]:
                keyword_score = self.bm25.score(query, idx)
                # Normalize to 0-1 range (approximate)
                keyword_score = min(keyword_score / 10.0, 1.0)
            
            # Semantic search
            if mode in [SearchMode.SEMANTIC, SearchMode.HYBRID] and query_embedding:
                doc_embedding = doc.get("embedding", [])
                if doc_embedding:
                    semantic_score = self._cosine_similarity(query_embedding, doc_embedding)
                    semantic_score = max(0, semantic_score)  # Ensure non-negative
            
            # Combine scores
            if mode == SearchMode.KEYWORD:
                combined_score = keyword_score
            elif mode == SearchMode.SEMANTIC:
                combined_score = semantic_score
            else:  # HYBRID
                combined_score = (
                    self.keyword_weight * keyword_score +
                    self.semantic_weight * semantic_score
                )
            
            if combined_score >= min_score:
                results.append(SearchResult(
                    chunk_id=doc["id"],
                    text=doc["text"],
                    score=combined_score,
                    keyword_score=keyword_score,
                    semantic_score=semantic_score,
                    metadata=doc.get("metadata", {}),
                ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]
    
    def get_stats(self) -> dict:
        """Get search engine statistics."""
        return {
            "total_documents": len(self.documents),
            "unique_terms": len(self.bm25.doc_freqs),
            "avg_doc_length": self.bm25.avg_doc_length,
            "keyword_weight": self.keyword_weight,
            "semantic_weight": self.semantic_weight,
            "default_mode": self.default_mode.value,
        }

