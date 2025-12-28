"""
Unit tests for Enhanced RAG components.

Tests chunking, hybrid search, and reranking.
"""

import pytest

from app.services.rag.chunker import SmartChunker, ChunkingStrategy, Chunk
from app.services.rag.hybrid_search import HybridSearchEngine, SearchMode, BM25, SearchResult
from app.services.rag.reranker import MockReranker, RerankedResult


# =============================================================================
# Chunker Tests
# =============================================================================


class TestSmartChunker:
    """Tests for SmartChunker."""
    
    @pytest.fixture
    def chunker(self):
        """Create a chunker with default settings."""
        return SmartChunker(chunk_size=200, chunk_overlap=20)
    
    def test_empty_text(self, chunker):
        """Test chunking empty text."""
        chunks = chunker.chunk("")
        assert chunks == []
    
    def test_short_text(self, chunker):
        """Test chunking text shorter than chunk size."""
        text = "This is a short text."
        chunks = chunker.chunk(text, doc_id="test")
        
        assert len(chunks) == 1
        assert chunks[0].text == text
    
    def test_fixed_size_chunking(self):
        """Test fixed size chunking strategy."""
        chunker = SmartChunker(
            chunk_size=50,
            chunk_overlap=10,
            strategy=ChunkingStrategy.FIXED_SIZE,
            min_chunk_size=20,  # Lower min to allow more chunks
        )
        
        text = "Word " * 30  # ~150 characters with words
        chunks = chunker.chunk(text, doc_id="test")
        
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk.text) <= 60  # Allow slight overflow at word boundaries
    
    def test_sentence_chunking(self):
        """Test sentence-based chunking."""
        chunker = SmartChunker(
            chunk_size=100,
            strategy=ChunkingStrategy.SENTENCE,
        )
        
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunker.chunk(text, doc_id="test")
        
        # Should group sentences together
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.text.endswith('.')
    
    def test_paragraph_chunking(self):
        """Test paragraph-based chunking."""
        chunker = SmartChunker(
            chunk_size=200,
            strategy=ChunkingStrategy.PARAGRAPH,
        )
        
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk(text, doc_id="test")
        
        assert len(chunks) >= 1
    
    def test_semantic_chunking(self):
        """Test semantic (section-aware) chunking."""
        chunker = SmartChunker(
            chunk_size=500,
            strategy=ChunkingStrategy.SEMANTIC,
        )
        
        text = """# Section 1
        Content for section 1.
        
        ## Section 1.1
        More content here.
        
        # Section 2
        Different section content."""
        
        chunks = chunker.chunk(text, doc_id="test")
        assert len(chunks) >= 1
    
    def test_hybrid_chunking(self):
        """Test hybrid chunking strategy."""
        chunker = SmartChunker(
            chunk_size=200,
            strategy=ChunkingStrategy.HYBRID,
        )
        
        text = """# Coverage Details
        
        Engine parts are covered including:
        - Pistons
        - Crankshaft
        - Valves
        
        # Exclusions
        
        The following are NOT covered:
        - Turbo modifications
        - Racing damage"""
        
        chunks = chunker.chunk(text, doc_id="test")
        assert len(chunks) >= 1
    
    def test_chunk_has_metadata(self, chunker):
        """Test that chunks include metadata."""
        text = "Some text content for testing metadata."
        chunks = chunker.chunk(text, doc_id="test", metadata={"source": "policy"})
        
        assert len(chunks) == 1
        assert "source" in chunks[0].metadata
        assert chunks[0].metadata["source"] == "policy"
    
    def test_chunk_ids_unique(self, chunker):
        """Test that chunk IDs are unique."""
        text = "First chunk. " * 20 + "Second chunk. " * 20
        chunks = chunker.chunk(text, doc_id="test")
        
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))  # All unique


class TestChunk:
    """Tests for Chunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating a chunk."""
        chunk = Chunk(
            id="chunk_1",
            text="Some text",
            index=0,
            start_char=0,
            end_char=9,
        )
        
        assert chunk.id == "chunk_1"
        assert chunk.text == "Some text"
        assert chunk.length == 9
    
    def test_chunk_to_dict(self):
        """Test converting chunk to dict."""
        chunk = Chunk(
            id="chunk_1",
            text="Some text",
            index=0,
            start_char=0,
            end_char=9,
            metadata={"key": "value"},
        )
        
        d = chunk.to_dict()
        assert d["id"] == "chunk_1"
        assert d["text"] == "Some text"
        assert d["metadata"]["key"] == "value"


# =============================================================================
# BM25 Tests
# =============================================================================


class TestBM25:
    """Tests for BM25 keyword search."""
    
    @pytest.fixture
    def bm25(self):
        """Create BM25 index with sample documents."""
        bm25 = BM25()
        documents = [
            "Engine coverage includes pistons and crankshaft.",
            "Exclusions include turbo and racing modifications.",
            "Deductible for engine repairs is 400 NIS.",
            "Towing service is included in roadside assistance.",
        ]
        bm25.fit(documents)
        return bm25
    
    def test_fit_documents(self, bm25):
        """Test fitting BM25 on documents."""
        assert len(bm25.corpus) == 4
        assert bm25.avg_doc_length > 0
    
    def test_search_returns_results(self, bm25):
        """Test that search returns results."""
        results = bm25.search("engine coverage")
        
        assert len(results) > 0
        # First result should be about engine
        assert results[0][1] > 0  # Score > 0
    
    def test_search_ranking(self, bm25):
        """Test that results are ranked by relevance."""
        results = bm25.search("turbo exclusions", top_k=4)
        
        # Results should be sorted by score descending
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_no_results(self, bm25):
        """Test search with no matching terms."""
        results = bm25.search("xyznonexistent")
        
        assert len(results) == 0
    
    def test_score_calculation(self, bm25):
        """Test individual document scoring."""
        # Document 0 contains "engine"
        score = bm25.score("engine", 0)
        assert score > 0
        
        # Document 1 doesn't contain "engine"
        score = bm25.score("engine", 1)
        assert score == 0


# =============================================================================
# Hybrid Search Tests
# =============================================================================


class TestHybridSearchEngine:
    """Tests for HybridSearchEngine."""
    
    @pytest.fixture
    def search_engine(self):
        """Create search engine with sample documents."""
        engine = HybridSearchEngine(
            keyword_weight=0.3,
            semantic_weight=0.7,
        )
        
        documents = [
            {
                "id": "chunk_1",
                "text": "Engine coverage includes pistons and crankshaft.",
                "embedding": [0.1] * 384,  # Mock embedding
                "metadata": {"policy_id": "POL-001"},
            },
            {
                "id": "chunk_2",
                "text": "Exclusions include turbo and racing modifications.",
                "embedding": [0.2] * 384,
                "metadata": {"policy_id": "POL-001"},
            },
            {
                "id": "chunk_3",
                "text": "Different policy content here.",
                "embedding": [0.3] * 384,
                "metadata": {"policy_id": "POL-002"},
            },
        ]
        
        engine.add_documents(documents)
        return engine
    
    def test_add_documents(self, search_engine):
        """Test adding documents to search engine."""
        assert len(search_engine.documents) == 3
    
    def test_keyword_search(self, search_engine):
        """Test keyword-only search."""
        results = search_engine.search(
            query="engine coverage",
            mode=SearchMode.KEYWORD,
        )
        
        assert len(results) > 0
        assert results[0].keyword_score > 0
    
    def test_semantic_search(self, search_engine):
        """Test semantic-only search."""
        query_embedding = [0.15] * 384  # Similar to chunk_1
        
        results = search_engine.search(
            query="engine parts",
            query_embedding=query_embedding,
            mode=SearchMode.SEMANTIC,
        )
        
        assert len(results) > 0
    
    def test_hybrid_search(self, search_engine):
        """Test hybrid (keyword + semantic) search."""
        query_embedding = [0.1] * 384
        
        results = search_engine.search(
            query="engine coverage",
            query_embedding=query_embedding,
            mode=SearchMode.HYBRID,
        )
        
        assert len(results) > 0
        # Should have both scores
        assert results[0].keyword_score >= 0
        assert results[0].semantic_score >= 0
    
    def test_filter_by_policy(self, search_engine):
        """Test filtering results by policy ID."""
        results = search_engine.search(
            query="content",
            mode=SearchMode.KEYWORD,
            policy_id="POL-002",
        )
        
        # Should only return chunks from POL-002
        for result in results:
            assert result.metadata.get("policy_id") == "POL-002"
    
    def test_remove_document(self, search_engine):
        """Test removing a document."""
        assert search_engine.remove_document("chunk_1") is True
        assert len(search_engine.documents) == 2
        
        # Should not find removed document
        assert search_engine.remove_document("chunk_1") is False
    
    def test_get_stats(self, search_engine):
        """Test getting search engine statistics."""
        stats = search_engine.get_stats()
        
        assert stats["total_documents"] == 3
        assert "keyword_weight" in stats
        assert "semantic_weight" in stats


# =============================================================================
# Reranker Tests
# =============================================================================


class TestMockReranker:
    """Tests for MockReranker."""
    
    @pytest.fixture
    def reranker(self):
        """Create mock reranker."""
        return MockReranker(original_weight=0.4, rerank_weight=0.6)
    
    def test_rerank_empty_results(self, reranker):
        """Test reranking empty results."""
        results = reranker.rerank("query", [])
        assert results == []
    
    def test_rerank_single_result(self, reranker):
        """Test reranking single result."""
        results = reranker.rerank(
            query="engine coverage",
            results=[{
                "chunk_id": "c1",
                "text": "Engine coverage includes pistons.",
                "score": 0.8,
            }],
        )
        
        assert len(results) == 1
        assert results[0].rank == 1
    
    def test_rerank_multiple_results(self, reranker):
        """Test reranking multiple results."""
        results = reranker.rerank(
            query="engine coverage deductible",
            results=[
                {"chunk_id": "c1", "text": "Unrelated content here.", "score": 0.9},
                {"chunk_id": "c2", "text": "Engine coverage includes deductible of 400 NIS.", "score": 0.5},
                {"chunk_id": "c3", "text": "Some other text.", "score": 0.7},
            ],
            top_k=3,
        )
        
        assert len(results) == 3
        # Results should be reranked
        assert all(r.final_score >= 0 for r in results)
        # Ranks should be assigned
        assert [r.rank for r in results] == [1, 2, 3]
    
    def test_rerank_boosts_insurance_terms(self, reranker):
        """Test that insurance terms get boosted."""
        results = reranker.rerank(
            query="coverage",
            results=[
                {"chunk_id": "c1", "text": "Random text without keywords.", "score": 0.8},
                {"chunk_id": "c2", "text": "Coverage and exclusions are defined here.", "score": 0.5},
            ],
        )
        
        # Document with "coverage" and "exclusions" should rank higher
        coverage_result = next(r for r in results if "coverage" in r.text.lower())
        assert coverage_result.rerank_score > 0
    
    def test_rerank_respects_top_k(self, reranker):
        """Test that reranker respects top_k limit."""
        results = reranker.rerank(
            query="test",
            results=[
                {"chunk_id": f"c{i}", "text": f"Text {i}", "score": 0.5}
                for i in range(10)
            ],
            top_k=3,
        )
        
        assert len(results) == 3


class TestRerankedResult:
    """Tests for RerankedResult dataclass."""
    
    def test_reranked_result_creation(self):
        """Test creating reranked result."""
        result = RerankedResult(
            chunk_id="c1",
            text="Some text",
            original_score=0.8,
            rerank_score=0.6,
            final_score=0.7,
            rank=1,
        )
        
        assert result.chunk_id == "c1"
        assert result.original_score == 0.8
        assert result.rank == 1
    
    def test_reranked_result_to_dict(self):
        """Test converting reranked result to dict."""
        result = RerankedResult(
            chunk_id="c1",
            text="Some text",
            original_score=0.8,
            rerank_score=0.6,
            final_score=0.7,
            rank=1,
            metadata={"key": "value"},
        )
        
        d = result.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["final_score"] == 0.7
        assert d["metadata"]["key"] == "value"

