"""
Unit tests for vector store implementations.

Tests both InMemoryVectorStore and PGVectorStore.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.vector_store.base import (
    ChunkType,
    DocumentChunk,
    VectorSearchResult,
)
from app.services.vector_store.memory_store import InMemoryVectorStore


# =============================================================================
# InMemoryVectorStore Tests
# =============================================================================


class TestInMemoryVectorStore:
    """Tests for InMemoryVectorStore."""

    @pytest.fixture
    def store(self):
        """Create a fresh store for each test."""
        return InMemoryVectorStore()

    @pytest.fixture
    def sample_chunk(self):
        """Create a sample chunk with embedding."""
        return DocumentChunk(
            id="test-chunk-1",
            text="This is a test chunk about engine coverage.",
            chunk_type=ChunkType.COVERAGE_INCLUSION,
            policy_id="POL-001",
            category="Engine",
            page_number=1,
            section_title="Engine Coverage",
            embedding=[0.1] * 384,  # MiniLM dimension
        )

    @pytest.mark.unit
    def test_add_chunk(self, store, sample_chunk):
        """Test adding a single chunk."""
        chunk_id = store.add(sample_chunk)
        
        assert chunk_id == sample_chunk.id
        assert store.count() == 1

    @pytest.mark.unit
    def test_add_chunk_without_embedding_raises(self, store):
        """Test that adding chunk without embedding raises error."""
        chunk = DocumentChunk(
            text="No embedding",
            chunk_type=ChunkType.RAW_TEXT,
        )
        
        with pytest.raises(ValueError, match="must have an embedding"):
            store.add(chunk)

    @pytest.mark.unit
    def test_add_many_chunks(self, store):
        """Test adding multiple chunks at once."""
        chunks = [
            DocumentChunk(
                id=f"chunk-{i}",
                text=f"Test chunk {i}",
                chunk_type=ChunkType.RAW_TEXT,
                policy_id="POL-001",
                embedding=[0.1 * i] * 384,
            )
            for i in range(5)
        ]
        
        ids = store.add_many(chunks)
        
        assert len(ids) == 5
        assert store.count() == 5

    @pytest.mark.unit
    def test_get_chunk(self, store, sample_chunk):
        """Test retrieving a chunk by ID."""
        store.add(sample_chunk)
        
        retrieved = store.get(sample_chunk.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_chunk.id
        assert retrieved.text == sample_chunk.text

    @pytest.mark.unit
    def test_get_nonexistent_chunk(self, store):
        """Test retrieving non-existent chunk returns None."""
        result = store.get("nonexistent-id")
        assert result is None

    @pytest.mark.unit
    def test_delete_chunk(self, store, sample_chunk):
        """Test deleting a chunk."""
        store.add(sample_chunk)
        assert store.count() == 1
        
        deleted = store.delete(sample_chunk.id)
        
        assert deleted is True
        assert store.count() == 0

    @pytest.mark.unit
    def test_delete_nonexistent_chunk(self, store):
        """Test deleting non-existent chunk returns False."""
        result = store.delete("nonexistent-id")
        assert result is False

    @pytest.mark.unit
    def test_delete_by_policy(self, store):
        """Test deleting all chunks for a policy."""
        # Add chunks for two policies
        for i in range(3):
            store.add(DocumentChunk(
                id=f"pol1-{i}",
                text=f"Policy 1 chunk {i}",
                policy_id="POL-001",
                embedding=[0.1] * 384,
            ))
        for i in range(2):
            store.add(DocumentChunk(
                id=f"pol2-{i}",
                text=f"Policy 2 chunk {i}",
                policy_id="POL-002",
                embedding=[0.2] * 384,
            ))
        
        assert store.count() == 5
        
        deleted = store.delete_by_policy("POL-001")
        
        assert deleted == 3
        assert store.count() == 2

    @pytest.mark.unit
    def test_search_basic(self, store, sample_chunk):
        """Test basic similarity search."""
        store.add(sample_chunk)
        
        # Search with same embedding should find it
        results = store.search(
            query_embedding=sample_chunk.embedding,
            top_k=5,
        )
        
        assert len(results) == 1
        assert results[0].chunk.id == sample_chunk.id
        assert results[0].score > 0.9  # Should be very similar

    @pytest.mark.unit
    def test_search_with_policy_filter(self, store):
        """Test search filtered by policy ID."""
        # Add chunks from different policies
        store.add(DocumentChunk(
            id="pol1-chunk",
            text="Policy 1 content",
            policy_id="POL-001",
            embedding=[0.1, 0.2, 0.3] + [0.0] * 381,
        ))
        store.add(DocumentChunk(
            id="pol2-chunk",
            text="Policy 2 content",
            policy_id="POL-002",
            embedding=[0.1, 0.2, 0.3] + [0.0] * 381,
        ))
        
        results = store.search(
            query_embedding=[0.1, 0.2, 0.3] + [0.0] * 381,
            policy_id="POL-001",
        )
        
        assert len(results) == 1
        assert results[0].chunk.policy_id == "POL-001"

    @pytest.mark.unit
    def test_search_with_chunk_type_filter(self, store):
        """Test search filtered by chunk type."""
        store.add(DocumentChunk(
            id="exclusion-chunk",
            text="This is excluded",
            chunk_type=ChunkType.EXCLUSION,
            embedding=[0.1] * 384,
        ))
        store.add(DocumentChunk(
            id="inclusion-chunk",
            text="This is included",
            chunk_type=ChunkType.INCLUSION,
            embedding=[0.1] * 384,
        ))
        
        results = store.search(
            query_embedding=[0.1] * 384,
            chunk_type=ChunkType.EXCLUSION,
        )
        
        assert len(results) == 1
        assert results[0].chunk.chunk_type == ChunkType.EXCLUSION

    @pytest.mark.unit
    def test_search_min_score_filter(self, store):
        """Test search with minimum score threshold."""
        store.add(DocumentChunk(
            id="similar-chunk",
            text="Very similar content",
            embedding=[0.9] * 384,
        ))
        store.add(DocumentChunk(
            id="dissimilar-chunk",
            text="Very different content",
            embedding=[-0.9] * 384,
        ))
        
        results = store.search(
            query_embedding=[0.9] * 384,
            min_score=0.5,
        )
        
        # Only similar chunk should pass threshold
        assert len(results) == 1
        assert results[0].chunk.id == "similar-chunk"

    @pytest.mark.unit
    def test_clear(self, store, sample_chunk):
        """Test clearing all chunks."""
        store.add(sample_chunk)
        assert store.count() > 0
        
        store.clear()
        
        assert store.count() == 0

    @pytest.mark.unit
    def test_get_all_policy_ids(self, store):
        """Test getting all unique policy IDs."""
        policies = ["POL-001", "POL-002", "POL-003"]
        for i, pol_id in enumerate(policies):
            store.add(DocumentChunk(
                id=f"chunk-{i}",
                text=f"Chunk for {pol_id}",
                policy_id=pol_id,
                embedding=[0.1 * i] * 384,
            ))
        
        result = store.get_all_policy_ids()
        
        assert set(result) == set(policies)

    @pytest.mark.unit
    def test_get_stats(self, store):
        """Test getting store statistics."""
        store.add(DocumentChunk(
            id="chunk-1",
            text="Exclusion chunk",
            chunk_type=ChunkType.EXCLUSION,
            policy_id="POL-001",
            embedding=[0.1] * 384,
        ))
        store.add(DocumentChunk(
            id="chunk-2",
            text="Inclusion chunk",
            chunk_type=ChunkType.INCLUSION,
            policy_id="POL-001",
            embedding=[0.2] * 384,
        ))
        
        stats = store.get_stats()
        
        assert stats["total_chunks"] == 2
        assert stats["total_policies"] == 1
        assert "exclusion" in stats["chunks_by_type"]
        assert "inclusion" in stats["chunks_by_type"]


# =============================================================================
# DocumentChunk Tests
# =============================================================================


class TestDocumentChunk:
    """Tests for DocumentChunk dataclass."""

    @pytest.mark.unit
    def test_chunk_creation(self):
        """Test creating a chunk with all fields."""
        chunk = DocumentChunk(
            id="test-id",
            text="Test content",
            chunk_type=ChunkType.EXCLUSION,
            policy_id="POL-001",
            category="Engine",
            page_number=5,
            section_title="Exclusions",
            metadata={"key": "value"},
        )
        
        assert chunk.id == "test-id"
        assert chunk.chunk_type == ChunkType.EXCLUSION
        assert chunk.page_number == 5

    @pytest.mark.unit
    def test_chunk_citation(self):
        """Test citation generation."""
        chunk = DocumentChunk(
            text="Test",
            page_number=10,
            section_title="Coverage Details",
            category="Engine",
        )
        
        citation = chunk.citation
        
        assert "Page 10" in citation
        assert "Coverage Details" in citation
        assert "Engine" in citation

    @pytest.mark.unit
    def test_chunk_citation_minimal(self):
        """Test citation with minimal info."""
        chunk = DocumentChunk(text="Test")
        
        assert chunk.citation == "Unspecified location"

    @pytest.mark.unit
    def test_chunk_to_dict(self):
        """Test converting chunk to dictionary."""
        chunk = DocumentChunk(
            id="test-id",
            text="Test",
            chunk_type=ChunkType.DEFINITION,
            policy_id="POL-001",
        )
        
        data = chunk.to_dict()
        
        assert data["id"] == "test-id"
        assert data["chunk_type"] == "definition"
        assert data["policy_id"] == "POL-001"

    @pytest.mark.unit
    def test_chunk_from_dict(self):
        """Test creating chunk from dictionary."""
        data = {
            "id": "test-id",
            "text": "Test content",
            "chunk_type": "exclusion",
            "policy_id": "POL-001",
        }
        
        chunk = DocumentChunk.from_dict(data)
        
        assert chunk.id == "test-id"
        assert chunk.chunk_type == ChunkType.EXCLUSION


# =============================================================================
# ChunkType Tests
# =============================================================================


class TestChunkType:
    """Tests for ChunkType enum."""

    @pytest.mark.unit
    def test_all_chunk_types_defined(self):
        """Verify all expected chunk types exist."""
        expected_types = [
            "POLICY_META",
            "COVERAGE_INCLUSION",
            "COVERAGE_EXCLUSION",
            "FINANCIAL_TERMS",
            "CLIENT_OBLIGATION",
            "SERVICE_NETWORK",
            "EXCLUSION",
            "INCLUSION",
            "DEFINITION",
            "LIMITATION",
            "PROCEDURE",
            "RAW_TEXT",
            "GENERAL",
        ]
        
        for type_name in expected_types:
            assert hasattr(ChunkType, type_name), f"Missing ChunkType: {type_name}"

    @pytest.mark.unit
    def test_chunk_type_values_are_strings(self):
        """Verify chunk type values are lowercase strings."""
        for chunk_type in ChunkType:
            assert isinstance(chunk_type.value, str)
            assert chunk_type.value == chunk_type.value.lower()
