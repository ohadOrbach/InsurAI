"""
Query reranking for improved retrieval quality.

Reranks initial retrieval results using more sophisticated
scoring to improve relevance.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RerankedResult:
    """A reranked search result."""
    
    chunk_id: str
    text: str
    original_score: float
    rerank_score: float
    final_score: float
    rank: int
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "original_score": self.original_score,
            "rerank_score": self.rerank_score,
            "final_score": self.final_score,
            "rank": self.rank,
            "metadata": self.metadata,
        }


class Reranker(ABC):
    """Abstract base class for rerankers."""
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """
        Rerank search results.
        
        Args:
            query: Original search query
            results: Initial search results with 'chunk_id', 'text', 'score'
            top_k: Number of results to return
            
        Returns:
            Reranked results
        """
        pass


class MockReranker(Reranker):
    """
    Mock reranker for development and testing.
    
    Uses heuristic scoring based on:
    - Query term overlap
    - Insurance-specific term boosting
    - Document structure signals
    """
    
    # Insurance-specific important terms
    BOOST_TERMS = {
        # Coverage terms
        "covered": 1.5,
        "coverage": 1.5,
        "included": 1.3,
        "inclusion": 1.3,
        # Exclusion terms
        "excluded": 1.5,
        "exclusion": 1.5,
        "not covered": 1.5,
        "exception": 1.3,
        # Financial terms
        "deductible": 1.4,
        "premium": 1.3,
        "cap": 1.3,
        "limit": 1.2,
        "copay": 1.3,
        # Policy terms
        "policy": 1.2,
        "warranty": 1.2,
        "claim": 1.3,
        "benefit": 1.2,
    }
    
    def __init__(
        self,
        original_weight: float = 0.4,
        rerank_weight: float = 0.6,
    ):
        """
        Initialize mock reranker.
        
        Args:
            original_weight: Weight for original score
            rerank_weight: Weight for rerank score
        """
        self.original_weight = original_weight
        self.rerank_weight = rerank_weight
    
    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase terms."""
        return set(re.findall(r'\b\w+\b', text.lower()))
    
    def _calculate_rerank_score(self, query: str, text: str) -> float:
        """
        Calculate reranking score based on heuristics.
        
        Args:
            query: Search query
            text: Document text
            
        Returns:
            Rerank score (0-1)
        """
        query_tokens = self._tokenize(query)
        text_lower = text.lower()
        text_tokens = self._tokenize(text)
        
        score = 0.0
        
        # 1. Query term overlap (Jaccard-like)
        if query_tokens and text_tokens:
            overlap = len(query_tokens & text_tokens)
            overlap_score = overlap / len(query_tokens)
            score += overlap_score * 0.4
        
        # 2. Exact phrase matching
        for query_term in query_tokens:
            if query_term in text_lower:
                score += 0.05
        
        # 3. Boost for insurance-specific terms
        for term, boost in self.BOOST_TERMS.items():
            if term in text_lower:
                score += 0.05 * boost
        
        # 4. Structural signals
        if text.strip().startswith(('#', '##', 'COVERAGE', 'EXCLUSION')):
            score += 0.1  # Section headers are important
        
        if re.search(r'\d+\s*(NIS|USD|\$)', text):
            score += 0.05  # Contains financial figures
        
        # 5. Length penalty (prefer moderate length)
        text_len = len(text)
        if 100 <= text_len <= 500:
            score += 0.05
        elif text_len < 50:
            score -= 0.05
        
        # Normalize to 0-1
        return min(max(score, 0), 1)
    
    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """
        Rerank search results using heuristic scoring.
        
        Args:
            query: Original search query
            results: Initial search results
            top_k: Number of results to return
            
        Returns:
            Reranked results
        """
        if not results:
            return []
        
        reranked = []
        
        for result in results:
            original_score = result.get("score", 0)
            text = result.get("text", "")
            
            rerank_score = self._calculate_rerank_score(query, text)
            
            final_score = (
                self.original_weight * original_score +
                self.rerank_weight * rerank_score
            )
            
            reranked.append(RerankedResult(
                chunk_id=result.get("chunk_id", result.get("id", "")),
                text=text,
                original_score=original_score,
                rerank_score=rerank_score,
                final_score=final_score,
                rank=0,  # Will be set after sorting
                metadata=result.get("metadata", {}),
            ))
        
        # Sort by final score
        reranked.sort(key=lambda x: x.final_score, reverse=True)
        
        # Assign ranks and limit to top_k
        for i, result in enumerate(reranked[:top_k]):
            result.rank = i + 1
        
        return reranked[:top_k]


class CrossEncoderReranker(Reranker):
    """
    Cross-encoder reranker using transformer models.
    
    For production use with sentence-transformers cross-encoders.
    Provides more accurate but slower reranking.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        original_weight: float = 0.3,
        rerank_weight: float = 0.7,
    ):
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: Hugging Face model name
            original_weight: Weight for original score
            rerank_weight: Weight for rerank score
        """
        self.model_name = model_name
        self.original_weight = original_weight
        self.rerank_weight = rerank_weight
        self._model = None
    
    @property
    def model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for CrossEncoderReranker. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model
    
    def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """
        Rerank using cross-encoder model.
        
        Args:
            query: Original search query
            results: Initial search results
            top_k: Number of results to return
            
        Returns:
            Reranked results
        """
        if not results:
            return []
        
        # Prepare query-document pairs
        pairs = [(query, r.get("text", "")) for r in results]
        
        # Get cross-encoder scores
        scores = self.model.predict(pairs)
        
        reranked = []
        
        for i, (result, ce_score) in enumerate(zip(results, scores)):
            original_score = result.get("score", 0)
            
            # Normalize cross-encoder score to 0-1
            rerank_score = 1 / (1 + pow(2.718, -ce_score))  # Sigmoid
            
            final_score = (
                self.original_weight * original_score +
                self.rerank_weight * rerank_score
            )
            
            reranked.append(RerankedResult(
                chunk_id=result.get("chunk_id", result.get("id", "")),
                text=result.get("text", ""),
                original_score=original_score,
                rerank_score=rerank_score,
                final_score=final_score,
                rank=0,
                metadata=result.get("metadata", {}),
            ))
        
        # Sort by final score
        reranked.sort(key=lambda x: x.final_score, reverse=True)
        
        # Assign ranks
        for i, result in enumerate(reranked[:top_k]):
            result.rank = i + 1
        
        return reranked[:top_k]

