"""
Semantic Search API Endpoints.

Provides natural language search capabilities over policy documents
using vector similarity search.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_policy_engine, get_policy_store
from app.services.vector_store import (
    ChunkType,
    InMemoryVectorStore,
    MockEmbeddingService,
    PolicyVectorizer,
    VectorSearchResult,
)

router = APIRouter()


def get_vectorizer() -> PolicyVectorizer:
    """Get the shared vectorizer from agent service."""
    from app.services.agent_service import get_agent_service
    return get_agent_service().vectorizer


# =============================================================================
# Request/Response Models
# =============================================================================


class SearchRequest(BaseModel):
    """Semantic search request."""
    
    query: str = Field(
        ...,
        description="Natural language query",
        min_length=3,
        max_length=500,
        examples=["What parts are covered under engine warranty?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return",
    )
    min_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)",
    )


class SearchResultItem(BaseModel):
    """Single search result item."""
    
    text: str
    chunk_type: str
    category: Optional[str] = None
    policy_id: Optional[str] = None
    score: float
    rank: int
    metadata: dict = {}


class SearchResponse(BaseModel):
    """Search response."""
    
    success: bool = True
    query: str
    results: list[SearchResultItem]
    total_results: int


class VectorizeRequest(BaseModel):
    """Request to vectorize a policy."""
    
    policy_id: str = Field(..., description="Policy ID to vectorize")


class VectorizeResponse(BaseModel):
    """Vectorization response."""
    
    success: bool = True
    policy_id: str
    chunks_created: int
    message: str


class VectorStoreStats(BaseModel):
    """Vector store statistics."""
    
    total_chunks: int
    total_policies: int
    embedding_dim: int
    chunks_by_type: dict[str, int]
    chunks_by_category: dict[str, int]


# =============================================================================
# Search Endpoints
# =============================================================================


@router.post(
    "/query",
    response_model=SearchResponse,
    summary="Semantic search across all policies",
    description="""
Perform a natural language search across all vectorized policies.

The search uses semantic similarity to find relevant policy chunks
that match the meaning of your query, not just keywords.

**Example queries:**
- "What parts are covered under engine warranty?"
- "Is turbo replacement covered?"
- "What is the deductible for electrical repairs?"
- "What maintenance is required to keep the policy valid?"
    """,
)
async def search_all_policies(request: SearchRequest):
    """Search across all vectorized policies."""
    vectorizer = get_vectorizer()
    
    if vectorizer.vector_store.count() == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No policies have been vectorized. Use POST /api/v1/search/vectorize/{policy_id} first.",
        )
    
    results = vectorizer.search(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
    )
    
    return SearchResponse(
        query=request.query,
        results=[
            SearchResultItem(
                text=r.chunk.text,
                chunk_type=r.chunk.chunk_type.value,
                category=r.chunk.category,
                policy_id=r.chunk.policy_id,
                score=round(r.score, 4),
                rank=r.rank,
                metadata=r.chunk.metadata,
            )
            for r in results
        ],
        total_results=len(results),
    )


@router.post(
    "/query/{policy_id}",
    response_model=SearchResponse,
    summary="Search within a specific policy",
    description="""
Search within a specific policy using natural language.

Returns chunks from the specified policy that semantically match your query.
    """,
)
async def search_policy(
    policy_id: str = Path(..., description="Policy ID to search"),
    request: SearchRequest = ...,
):
    """Search within a specific policy."""
    vectorizer = get_vectorizer()
    
    # Check if policy is vectorized
    if vectorizer.vector_store.count_by_policy(policy_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' has not been vectorized. Use POST /api/v1/search/vectorize/{policy_id} first.",
        )
    
    results = vectorizer.search(
        query=request.query,
        policy_id=policy_id,
        top_k=request.top_k,
        min_score=request.min_score,
    )
    
    return SearchResponse(
        query=request.query,
        results=[
            SearchResultItem(
                text=r.chunk.text,
                chunk_type=r.chunk.chunk_type.value,
                category=r.chunk.category,
                policy_id=r.chunk.policy_id,
                score=round(r.score, 4),
                rank=r.rank,
                metadata=r.chunk.metadata,
            )
            for r in results
        ],
        total_results=len(results),
    )


@router.get(
    "/query/{policy_id}",
    response_model=SearchResponse,
    summary="Quick semantic search (GET)",
    description="Quick semantic search using GET request with query parameter.",
)
async def search_policy_quick(
    policy_id: str = Path(..., description="Policy ID"),
    q: str = Query(..., min_length=3, description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20),
):
    """Quick search via GET."""
    vectorizer = get_vectorizer()
    
    if vectorizer.vector_store.count_by_policy(policy_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' has not been vectorized.",
        )
    
    results = vectorizer.search(
        query=q,
        policy_id=policy_id,
        top_k=top_k,
    )
    
    return SearchResponse(
        query=q,
        results=[
            SearchResultItem(
                text=r.chunk.text,
                chunk_type=r.chunk.chunk_type.value,
                category=r.chunk.category,
                policy_id=r.chunk.policy_id,
                score=round(r.score, 4),
                rank=r.rank,
                metadata=r.chunk.metadata,
            )
            for r in results
        ],
        total_results=len(results),
    )


# =============================================================================
# Vectorization Endpoints
# =============================================================================


@router.post(
    "/vectorize/{policy_id}",
    response_model=VectorizeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Vectorize a policy for search",
    description="""
Vectorize a policy document to enable semantic search.

This creates searchable chunks from:
- Policy metadata
- Coverage inclusions and exclusions
- Financial terms (deductibles, caps)
- Client obligations and restrictions
- Service network information
    """,
)
async def vectorize_policy(
    policy_id: str = Path(..., description="Policy ID to vectorize"),
):
    """Vectorize a policy for semantic search."""
    # Get policy from store
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}. Load a policy first.",
        )
    
    vectorizer = get_vectorizer()
    
    # Remove existing vectors for this policy (re-vectorize)
    removed = vectorizer.remove_policy(policy_id)
    if removed > 0:
        pass  # Policy was re-vectorized
    
    # Vectorize the policy
    chunks_created = vectorizer.vectorize_policy(engine.policy)
    
    return VectorizeResponse(
        policy_id=policy_id,
        chunks_created=chunks_created,
        message=f"Policy vectorized successfully with {chunks_created} searchable chunks",
    )


@router.delete(
    "/vectorize/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove policy vectors",
    description="Remove all vector chunks for a policy.",
)
async def remove_policy_vectors(
    policy_id: str = Path(..., description="Policy ID"),
):
    """Remove policy vectors from the store."""
    vectorizer = get_vectorizer()
    removed = vectorizer.remove_policy(policy_id)
    
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vectors found for policy: {policy_id}",
        )
    
    return None


# =============================================================================
# Statistics Endpoints
# =============================================================================


@router.get(
    "/stats",
    response_model=VectorStoreStats,
    summary="Get vector store statistics",
    description="Get statistics about the vector store including chunk counts by type and category.",
)
async def get_vector_stats():
    """Get vector store statistics."""
    vectorizer = get_vectorizer()
    stats = vectorizer.get_stats()
    
    return VectorStoreStats(
        total_chunks=stats.get("total_chunks", 0),
        total_policies=stats.get("total_policies", 0),
        embedding_dim=stats.get("embedding_dim", 384),
        chunks_by_type=stats.get("chunks_by_type", {}),
        chunks_by_category=stats.get("chunks_by_category", {}),
    )


@router.get(
    "/policies",
    summary="List vectorized policies",
    description="Get list of all policies that have been vectorized.",
)
async def list_vectorized_policies():
    """List all vectorized policies."""
    vectorizer = get_vectorizer()
    store = vectorizer.vector_store
    
    if hasattr(store, 'get_all_policy_ids'):
        policy_ids = store.get_all_policy_ids()
        policies = []
        
        for pid in policy_ids:
            count = store.count_by_policy(pid) if hasattr(store, 'count_by_policy') else 0
            policies.append({
                "policy_id": pid,
                "chunk_count": count,
            })
        
        return {
            "success": True,
            "total_policies": len(policies),
            "policies": policies,
        }
    
    return {
        "success": True,
        "total_policies": 0,
        "policies": [],
    }


@router.get(
    "/debug/chunks/{policy_id}",
    summary="Debug: View chunks for a policy",
    description="Debug endpoint to view all chunks for a specific policy.",
)
async def debug_view_chunks(
    policy_id: str = Path(..., description="Policy ID"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
    limit: int = Query(20, description="Max chunks to return"),
):
    """View chunks for debugging."""
    vectorizer = get_vectorizer()
    store = vectorizer.vector_store
    
    chunks = []
    for chunk in store._chunks.values():
        if chunk.policy_id == policy_id:
            if chunk_type and chunk.chunk_type.value != chunk_type:
                continue
            chunks.append({
                "id": chunk.id[:8],
                "type": chunk.chunk_type.value,
                "page": chunk.page_number,
                "section": chunk.section_title,
                "category": chunk.category,
                "text": chunk.text[:300] + "..." if len(chunk.text) > 300 else chunk.text,
                "citation": chunk.citation,
            })
            if len(chunks) >= limit:
                break
    
    # Group by type
    type_counts = {}
    for c in store._chunks.values():
        if c.policy_id == policy_id:
            t = c.chunk_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
    
    return {
        "success": True,
        "policy_id": policy_id,
        "total_chunks": sum(type_counts.values()),
        "chunks_by_type": type_counts,
        "sample_chunks": chunks,
    }

