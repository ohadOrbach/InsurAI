"""
Embedding service for generating text vectors.

Supports:
- Sentence Transformers (production)
- Mock embeddings (development/testing)
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """Abstract base class for embedding generation."""
    
    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Get the embedding dimension."""
        pass
    
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: The text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        pass
    
    @abstractmethod
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass


class SentenceTransformerEmbedding(EmbeddingService):
    """
    Embedding service using Sentence Transformers.
    
    Uses pre-trained models optimized for semantic similarity.
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformers model
            device: Device to use ('cpu', 'cuda', etc.)
        """
        self.model_name = model_name
        self._model = None
        self._device = device
        self._dim: Optional[int] = None
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self._device,
                )
                self._dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Loaded embedding model: {self.model_name} (dim={self._dim})")
            except ImportError as e:
                logger.error("sentence-transformers not installed")
                raise ImportError(
                    "sentence-transformers required. Install with: pip install sentence-transformers"
                ) from e
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension."""
        if self._dim is None:
            self._load_model()
        return self._dim
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class GeminiEmbeddingService(EmbeddingService):
    """
    Embedding service using Google Gemini's text-embedding-004.
    
    RECOMMENDED: Since you already have GOOGLE_API_KEY, this is the easiest upgrade.
    
    Benefits:
    - Long context (2048 tokens input, much better than MiniLM's 256)
    - Semantically superior for legal/insurance text
    - Uses same API key as your LLM (no additional cost complexity)
    - 768 dimensional output
    
    Model: models/text-embedding-004
    """
    
    def __init__(
        self,
        model_name: str = "models/text-embedding-004",
        api_key: Optional[str] = None,
    ):
        """
        Initialize Gemini embedding service.
        
        Args:
            model_name: Gemini embedding model name
            api_key: Google API key (or uses GOOGLE_API_KEY env var)
        """
        self.model_name = model_name
        self._client = None
        self._api_key = api_key
        self._dim = 768  # text-embedding-004 outputs 768 dimensions
    
    def _get_client(self):
        """Lazy load the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                import os
                
                api_key = self._api_key or os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not set")
                
                genai.configure(api_key=api_key)
                self._client = genai
                logger.info(f"Initialized Gemini embedding client with model: {self.model_name}")
            except ImportError as e:
                logger.error("google-generativeai package not installed")
                raise ImportError("google-generativeai required. Install with: pip install google-generativeai") from e
        return self._client
    
    @property
    def embedding_dim(self) -> int:
        return self._dim
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding using Gemini API."""
        client = self._get_client()
        
        # Gemini can handle long text, but let's be safe
        max_chars = 10000  # ~2k tokens
        if len(text) > max_chars:
            text = text[:max_chars]
        
        result = client.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_document",
        )
        
        return result['embedding']
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        client = self._get_client()
        
        max_chars = 10000
        processed_texts = [t[:max_chars] if len(t) > max_chars else t for t in texts]
        
        # Gemini doesn't have batch embedding, so we do it one by one
        # But it's still fast due to the API being optimized
        embeddings = []
        for text in processed_texts:
            result = client.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
            )
            embeddings.append(result['embedding'])
        
        return embeddings
    
    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a search query (different task type)."""
        client = self._get_client()
        
        result = client.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_query",  # Optimized for queries
        )
        
        return result['embedding']


class BGEEmbeddingService(EmbeddingService):
    """
    Embedding service using BAAI/bge-m3 (Best Open Source Option).
    
    Benefits:
    - 8192 token context (vs MiniLM's 256!)
    - Completely local/free (no API costs)
    - Multilingual support
    - 1024 dimensional output
    
    Use this if you want to keep embeddings strictly local.
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: Optional[str] = None,
    ):
        """
        Initialize BGE embedding service.
        
        Args:
            model_name: HuggingFace model name
            device: Device to use ('cpu', 'cuda', etc.)
        """
        self.model_name = model_name
        self._model = None
        self._device = device
        self._dim = 1024  # bge-m3 outputs 1024 dimensions
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self._device,
                )
                logger.info(f"Loaded BGE embedding model: {self.model_name} (dim={self._dim})")
            except ImportError as e:
                logger.error("sentence-transformers not installed")
                raise ImportError(
                    "sentence-transformers required. Install with: pip install sentence-transformers"
                ) from e
    
    @property
    def embedding_dim(self) -> int:
        return self._dim
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class OpenAIEmbeddingService(EmbeddingService):
    """
    Embedding service using OpenAI's text-embedding models.
    
    Benefits:
    - Higher context window (8k tokens)
    - Better semantic understanding for legal/insurance text
    - No local GPU required
    
    Models:
    - text-embedding-3-small: 1536 dim, $0.02/1M tokens
    - text-embedding-3-large: 3072 dim, $0.13/1M tokens
    """
    
    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
    ):
        """
        Initialize OpenAI embedding service.
        
        Args:
            model_name: OpenAI embedding model name
            api_key: OpenAI API key (or uses OPENAI_API_KEY env var)
        """
        self.model_name = model_name
        self._client = None
        self._api_key = api_key
        
        # Dimensions per model
        self._dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        self._dim = self._dims.get(model_name, 1536)
    
    def _get_client(self):
        """Lazy load the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                import os
                
                api_key = self._api_key or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not set")
                
                self._client = OpenAI(api_key=api_key)
                logger.info(f"Initialized OpenAI embedding client with model: {self.model_name}")
            except ImportError as e:
                logger.error("openai package not installed")
                raise ImportError("openai required. Install with: pip install openai") from e
        return self._client
    
    @property
    def embedding_dim(self) -> int:
        return self._dim
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API."""
        client = self._get_client()
        
        # Truncate text if too long (OpenAI handles this, but we can be explicit)
        max_chars = 8000 * 4  # ~8k tokens * ~4 chars/token
        if len(text) > max_chars:
            text = text[:max_chars]
        
        response = client.embeddings.create(
            model=self.model_name,
            input=text,
        )
        
        return response.data[0].embedding
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a batch."""
        client = self._get_client()
        
        # Truncate texts if needed
        max_chars = 8000 * 4
        processed_texts = [t[:max_chars] if len(t) > max_chars else t for t in texts]
        
        # OpenAI batch limit is 2048 texts
        batch_size = 2048
        all_embeddings = []
        
        for i in range(0, len(processed_texts), batch_size):
            batch = processed_texts[i:i + batch_size]
            response = client.embeddings.create(
                model=self.model_name,
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])
        
        return all_embeddings


class MockEmbeddingService(EmbeddingService):
    """
    Mock embedding service for testing and development.
    
    Generates deterministic pseudo-embeddings based on text hash.
    Useful when you don't want to load heavy ML models.
    """
    
    def __init__(self, dim: int = 384):
        """
        Initialize mock embedding service.
        
        Args:
            dim: Embedding dimension (default matches all-MiniLM-L6-v2)
        """
        self._dim = dim
    
    @property
    def embedding_dim(self) -> int:
        return self._dim
    
    def _text_to_seed(self, text: str) -> int:
        """Convert text to deterministic seed."""
        hash_bytes = hashlib.md5(text.encode()).digest()
        return int.from_bytes(hash_bytes[:4], byteorder='big')
    
    def embed(self, text: str) -> list[float]:
        """Generate mock embedding from text hash."""
        seed = self._text_to_seed(text)
        rng = np.random.RandomState(seed)
        
        # Generate normalized random vector
        embedding = rng.randn(self._dim)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for multiple texts."""
        return [self.embed(text) for text in texts]


class CachedEmbeddingService(EmbeddingService):
    """
    Wrapper that caches embeddings to avoid recomputation.
    """
    
    def __init__(
        self,
        base_service: EmbeddingService,
        max_cache_size: int = 10000,
    ):
        """
        Initialize cached embedding service.
        
        Args:
            base_service: The underlying embedding service
            max_cache_size: Maximum number of embeddings to cache
        """
        self._base = base_service
        self._cache: dict[str, list[float]] = {}
        self._max_size = max_cache_size
    
    @property
    def embedding_dim(self) -> int:
        return self._base.embedding_dim
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def embed(self, text: str) -> list[float]:
        """Get embedding, using cache if available."""
        key = self._cache_key(text)
        
        if key in self._cache:
            return self._cache[key]
        
        embedding = self._base.embed(text)
        
        # Add to cache if not full
        if len(self._cache) < self._max_size:
            self._cache[key] = embedding
        
        return embedding
    
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings, using cache where available."""
        results = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache first
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append(None)  # Placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)
        
        # Embed uncached texts
        if uncached_texts:
            new_embeddings = self._base.embed_many(uncached_texts)
            
            for idx, embedding, text in zip(uncached_indices, new_embeddings, uncached_texts):
                results[idx] = embedding
                
                # Cache if not full
                if len(self._cache) < self._max_size:
                    key = self._cache_key(text)
                    self._cache[key] = embedding
        
        return results
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
    
    @property
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

