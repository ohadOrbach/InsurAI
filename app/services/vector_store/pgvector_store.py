"""
PostgreSQL + PGVector store implementation.

Provides persistent vector storage that survives server restarts.
Uses PostgreSQL with the pgvector extension for efficient similarity search.

Key Benefits:
- Persistent storage (data survives restarts)
- Scales to millions of vectors
- ACID transactions
- Concurrent access from multiple instances
"""

import logging
from typing import Optional
import json

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

from .base import ChunkType, DocumentChunk, VectorSearchResult, VectorStore
from datetime import datetime

logger = logging.getLogger(__name__)

Base = declarative_base()


def create_vector_chunk_model(embedding_dim: int = 768):
    """
    Create a VectorChunkModel with the correct embedding dimension.
    
    This is needed because SQLAlchemy models have fixed column definitions,
    but we want to support different embedding dimensions:
    - 768 for Gemini text-embedding-004
    - 1024 for BAAI/bge-m3
    - 1536 for OpenAI text-embedding-3-small
    - 384 for all-MiniLM-L6-v2
    """
    
    class VectorChunkModel(Base):
        """SQLAlchemy model for vector chunks stored in PostgreSQL."""
        
        __tablename__ = "vector_chunks"
        __table_args__ = {'extend_existing': True}
        
        id = Column(String, primary_key=True)
        text = Column(Text, nullable=False)
        chunk_type = Column(String, default="general")
        policy_id = Column(String, index=True)
        category = Column(String, index=True)
        page_number = Column(Integer)
        section_title = Column(String)
        chunk_metadata = Column(JSON, default={})  # Renamed from 'metadata' (reserved)
        embedding = Column(Vector(embedding_dim))  # Dynamic dimension!
        created_at = Column(DateTime, default=datetime.utcnow)
        
        def to_document_chunk(self) -> DocumentChunk:
            """Convert to DocumentChunk dataclass."""
            return DocumentChunk(
                id=self.id,
                text=self.text,
                chunk_type=ChunkType(self.chunk_type),
                policy_id=self.policy_id,
                category=self.category,
                page_number=self.page_number,
                section_title=self.section_title,
                metadata=self.chunk_metadata or {},
                embedding=list(self.embedding) if self.embedding is not None else None,
                created_at=self.created_at,
            )
    
    return VectorChunkModel


class PGVectorStore(VectorStore):
    """
    PostgreSQL + PGVector based vector store.
    
    Features:
    - Persistent storage with PostgreSQL
    - Efficient vector similarity search via pgvector
    - ACID transactions
    - Concurrent access support
    - Automatic index creation for fast search
    
    Requires:
    - PostgreSQL 11+ with pgvector extension
    - Run: CREATE EXTENSION IF NOT EXISTS vector;
    """
    
    def __init__(
        self,
        database_url: str,
        embedding_dim: int = 768,  # Gemini default (was 384 for MiniLM)
        echo: bool = False,
    ):
        """
        Initialize PGVector store.
        
        Args:
            database_url: PostgreSQL connection string
            embedding_dim: Dimension of embeddings:
                - 768 for Gemini text-embedding-004 (default)
                - 1024 for BAAI/bge-m3
                - 1536 for OpenAI text-embedding-3-small
                - 384 for all-MiniLM-L6-v2 (legacy)
            echo: Log SQL queries
        """
        self.database_url = database_url
        self.embedding_dim = embedding_dim
        
        # Create engine
        self.engine = create_engine(database_url, echo=echo)
        self.Session = sessionmaker(bind=self.engine)
        
        # Create the model class with correct dimension
        self.VectorChunkModel = create_vector_chunk_model(embedding_dim)
        
        # Create tables
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables and extensions."""
        try:
            # Create pgvector extension (requires superuser or extension creator)
            with self.engine.connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not create pgvector extension (may already exist): {e}")
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Create vector index for fast similarity search
        try:
            with self.engine.connect() as conn:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS vector_chunks_embedding_idx 
                    ON vector_chunks 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not create vector index: {e}")
        
        logger.info("PGVector store initialized")
    
    def add(self, chunk: DocumentChunk) -> str:
        """Add a single chunk to the store."""
        if chunk.embedding is None:
            raise ValueError("Chunk must have an embedding")
        
        session = self.Session()
        try:
            model = self.VectorChunkModel(
                id=chunk.id,
                text=chunk.text,
                chunk_type=chunk.chunk_type.value,
                policy_id=chunk.policy_id,
                category=chunk.category,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                chunk_metadata=chunk.metadata,
                embedding=chunk.embedding,
                created_at=chunk.created_at,
            )
            session.merge(model)  # merge handles upsert
            session.commit()
            return chunk.id
        finally:
            session.close()
    
    def add_many(self, chunks: list[DocumentChunk]) -> list[str]:
        """Add multiple chunks in a batch."""
        session = self.Session()
        ids = []
        try:
            for chunk in chunks:
                if chunk.embedding is None:
                    raise ValueError(f"Chunk {chunk.id} must have an embedding")
                
                model = self.VectorChunkModel(
                    id=chunk.id,
                    text=chunk.text,
                    chunk_type=chunk.chunk_type.value,
                    policy_id=chunk.policy_id,
                    category=chunk.category,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    chunk_metadata=chunk.metadata,
                    embedding=chunk.embedding,
                    created_at=chunk.created_at,
                )
                session.merge(model)
                ids.append(chunk.id)
            
            session.commit()
            logger.info(f"Added {len(ids)} chunks to PGVector store")
            return ids
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Get a chunk by ID."""
        session = self.Session()
        try:
            model = session.query(self.VectorChunkModel).filter_by(id=chunk_id).first()
            return model.to_document_chunk() if model else None
        finally:
            session.close()
    
    def delete(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        session = self.Session()
        try:
            result = session.query(self.VectorChunkModel).filter_by(id=chunk_id).delete()
            session.commit()
            return result > 0
        finally:
            session.close()
    
    def delete_by_policy(self, policy_id: str) -> int:
        """Delete all chunks for a policy."""
        session = self.Session()
        try:
            count = session.query(self.VectorChunkModel).filter_by(policy_id=policy_id).delete()
            session.commit()
            logger.info(f"Deleted {count} chunks for policy {policy_id}")
            return count
        finally:
            session.close()
    
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
        
        Uses pgvector's <=> operator for cosine distance (1 - similarity).
        """
        session = self.Session()
        try:
            # Build query with filters
            query = session.query(
                self.VectorChunkModel,
                self.VectorChunkModel.embedding.cosine_distance(query_embedding).label("distance")
            )
            
            if policy_id:
                query = query.filter(self.VectorChunkModel.policy_id == policy_id)
            if chunk_type:
                query = query.filter(self.VectorChunkModel.chunk_type == chunk_type.value)
            if category:
                query = query.filter(self.VectorChunkModel.category == category)
            
            # Order by distance (lower = more similar)
            query = query.order_by("distance").limit(top_k * 2)  # Get extra for filtering
            
            results = []
            for i, (model, distance) in enumerate(query.all()):
                # Convert distance to similarity score (cosine distance is 1 - similarity)
                score = 1 - distance
                
                if score >= min_score:
                    results.append(VectorSearchResult(
                        chunk=model.to_document_chunk(),
                        score=score,
                        rank=len(results) + 1,
                    ))
                
                if len(results) >= top_k:
                    break
            
            return results
        finally:
            session.close()
    
    def clear(self) -> None:
        """Clear all chunks from the store."""
        session = self.Session()
        try:
            session.query(self.VectorChunkModel).delete()
            session.commit()
            logger.info("Cleared all chunks from PGVector store")
        finally:
            session.close()
    
    def count(self) -> int:
        """Get total number of chunks."""
        session = self.Session()
        try:
            return session.query(self.VectorChunkModel).count()
        finally:
            session.close()
    
    def count_by_policy(self, policy_id: str) -> int:
        """Get number of chunks for a specific policy."""
        session = self.Session()
        try:
            return session.query(self.VectorChunkModel).filter_by(policy_id=policy_id).count()
        finally:
            session.close()
    
    def get_all_policy_ids(self) -> list[str]:
        """Get all unique policy IDs in the store."""
        session = self.Session()
        try:
            results = session.query(self.VectorChunkModel.policy_id).distinct().all()
            return [r[0] for r in results if r[0] is not None]
        finally:
            session.close()
    
    def get_chunks_by_policy(self, policy_id: str) -> list[DocumentChunk]:
        """Get all chunks for a policy."""
        session = self.Session()
        try:
            models = session.query(self.VectorChunkModel).filter_by(policy_id=policy_id).all()
            return [m.to_document_chunk() for m in models]
        finally:
            session.close()
    
    def get_stats(self) -> dict:
        """Get store statistics."""
        session = self.Session()
        try:
            from sqlalchemy import func
            
            total = session.query(self.VectorChunkModel).count()
            policies = session.query(func.count(func.distinct(self.VectorChunkModel.policy_id))).scalar()
            
            # Count by type
            type_counts = session.query(
                self.VectorChunkModel.chunk_type,
                func.count(self.VectorChunkModel.id)
            ).group_by(self.VectorChunkModel.chunk_type).all()
            
            return {
                "total_chunks": total,
                "total_policies": policies,
                "chunks_by_type": {t: c for t, c in type_counts},
                "storage": "pgvector",
                "persistent": True,
            }
        finally:
            session.close()


# =============================================================================
# Factory Function
# =============================================================================

_pgvector_store: Optional[PGVectorStore] = None


def get_pgvector_store(database_url: Optional[str] = None) -> PGVectorStore:
    """Get or create the global PGVector store instance."""
    global _pgvector_store
    
    if _pgvector_store is None:
        from app.core.config import settings
        
        url = database_url or settings.DATABASE_URL
        
        # Convert async URL to sync if needed
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "")
        
        _pgvector_store = PGVectorStore(
            database_url=url,
            embedding_dim=384,  # MiniLM default
        )
        logger.info(f"PGVector store created with database: {url[:50]}...")
    
    return _pgvector_store

