"""
Policy Vectorizer - Chunks and vectorizes policy documents.

Transforms PolicyDocument objects into searchable vector chunks.

PRODUCTION-READY:
- Supports PGVector for persistent storage
- Supports OpenAI embeddings for 8k context window
- Configurable via environment variables
"""

import logging
from typing import Optional

from app.schema import PolicyDocument

from .base import ChunkType, DocumentChunk, VectorSearchResult, VectorStore
from .embeddings import (
    EmbeddingService, 
    MockEmbeddingService,
    SentenceTransformerEmbedding,
    OpenAIEmbeddingService,
    GeminiEmbeddingService,
    BGEEmbeddingService,
    CachedEmbeddingService,
)
from .memory_store import InMemoryVectorStore

logger = logging.getLogger(__name__)


class PolicyVectorizer:
    """
    Vectorizes policy documents for semantic search.
    
    Creates searchable chunks from:
    - Policy metadata
    - Coverage inclusions/exclusions per category
    - Financial terms
    - Client obligations
    - Service network info
    
    PRODUCTION FEATURES:
    - PGVector support for persistent storage
    - OpenAI embeddings for 8k context (better for legal text)
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        use_mock: bool = False,  # Changed default to False for production
    ):
        """
        Initialize the policy vectorizer.
        
        Args:
            vector_store: Vector store to use (from config if None)
            embedding_service: Embedding service (from config if None)
            use_mock: Use mock embedding service for development
        """
        # Get config
        from app.core.config import settings
        
        # Initialize vector store from config if not provided
        if vector_store is None:
            self.vector_store = self._get_vector_store_from_config(settings)
        else:
            self.vector_store = vector_store
        
        # Initialize embedding service from config if not provided
        if embedding_service is None:
            if use_mock:
                self.embedding_service = MockEmbeddingService()
            else:
                self.embedding_service = self._get_embedding_service_from_config(settings)
        else:
            self.embedding_service = embedding_service
        
        logger.info(
            f"PolicyVectorizer initialized: "
            f"store={type(self.vector_store).__name__}, "
            f"embeddings={type(self.embedding_service).__name__}"
        )
    
    def _get_vector_store_from_config(self, settings) -> VectorStore:
        """Get vector store based on config settings."""
        store_type = settings.VECTOR_STORE_TYPE.lower()
        
        if store_type == "pgvector":
            try:
                from .pgvector_store import PGVectorStore
                
                # Get embedding dimension based on embedding provider
                provider = settings.EMBEDDING_PROVIDER.lower()
                embedding_dims = {
                    "gemini": 768,       # text-embedding-004
                    "bge": 1024,         # BAAI/bge-m3
                    "openai": 1536,      # text-embedding-3-small
                    "sentence_transformer": 384,  # all-MiniLM-L6-v2
                }
                embedding_dim = embedding_dims.get(provider, 768)  # Default to Gemini
                
                return PGVectorStore(
                    database_url=settings.DATABASE_URL,
                    embedding_dim=embedding_dim,
                )
            except Exception as e:
                logger.warning(f"PGVector not available, falling back to memory: {e}")
                return InMemoryVectorStore()
        else:
            return InMemoryVectorStore()
    
    def _get_embedding_service_from_config(self, settings) -> EmbeddingService:
        """Get embedding service based on config settings."""
        provider = settings.EMBEDDING_PROVIDER.lower()
        
        if provider == "gemini":
            # RECOMMENDED: Uses same GOOGLE_API_KEY as your LLM
            try:
                base_service = GeminiEmbeddingService(
                    model_name=settings.EMBEDDING_MODEL or "models/text-embedding-004",
                    api_key=settings.GOOGLE_API_KEY or None,
                )
                logger.info("Using Gemini embeddings (768d, 2048 token context)")
                return CachedEmbeddingService(base_service)
            except Exception as e:
                logger.warning(f"Gemini embeddings not available: {e}")
                return self._get_fallback_embedding_service()
        
        elif provider == "bge":
            # Best open source option: 8192 token context window
            try:
                base_service = BGEEmbeddingService(
                    model_name=settings.EMBEDDING_MODEL or "BAAI/bge-m3",
                )
                logger.info("Using BGE embeddings (1024d, 8192 token context)")
                return CachedEmbeddingService(base_service)
            except Exception as e:
                logger.warning(f"BGE embeddings not available: {e}")
                return self._get_fallback_embedding_service()
        
        elif provider == "openai":
            try:
                base_service = OpenAIEmbeddingService(
                    model_name=settings.EMBEDDING_MODEL or "text-embedding-3-small",
                    api_key=settings.OPENAI_API_KEY or None,
                )
                logger.info("Using OpenAI embeddings (1536d, 8192 token context)")
                return CachedEmbeddingService(base_service)
            except Exception as e:
                logger.warning(f"OpenAI embeddings not available: {e}")
                return self._get_fallback_embedding_service()
        else:
            return self._get_fallback_embedding_service()
    
    def _get_fallback_embedding_service(self) -> EmbeddingService:
        """Get fallback embedding service (SentenceTransformer or Mock)."""
        try:
            base_service = SentenceTransformerEmbedding()
            return CachedEmbeddingService(base_service)
        except ImportError:
            logger.warning("sentence-transformers not available, using mock embeddings")
            return MockEmbeddingService()
    
    def vectorize_policy(self, policy: PolicyDocument) -> int:
        """
        Vectorize a policy document and add to vector store.
        
        Args:
            policy: The PolicyDocument to vectorize
            
        Returns:
            Number of chunks created
        """
        policy_id = policy.policy_meta.policy_id
        chunks = []
        
        # 1. Policy metadata chunk
        meta_text = self._build_meta_text(policy)
        chunks.append(DocumentChunk(
            text=meta_text,
            chunk_type=ChunkType.POLICY_META,
            policy_id=policy_id,
            metadata={
                "provider": policy.policy_meta.provider_name,
                "type": policy.policy_meta.policy_type,
                "status": policy.policy_meta.status.value,
            },
        ))
        
        # 2. Coverage chunks per category
        for coverage in policy.coverage_details:
            # Inclusions chunk
            if coverage.items_included:
                inclusion_text = self._build_inclusion_text(coverage)
                chunks.append(DocumentChunk(
                    text=inclusion_text,
                    chunk_type=ChunkType.COVERAGE_INCLUSION,
                    policy_id=policy_id,
                    category=coverage.category,
                    metadata={
                        "items": coverage.items_included,
                        "deductible": coverage.financial_terms.deductible,
                        "cap": coverage.financial_terms.coverage_cap,
                    },
                ))
            
            # Exclusions chunk
            if coverage.items_excluded:
                exclusion_text = self._build_exclusion_text(coverage)
                chunks.append(DocumentChunk(
                    text=exclusion_text,
                    chunk_type=ChunkType.COVERAGE_EXCLUSION,
                    policy_id=policy_id,
                    category=coverage.category,
                    metadata={
                        "items": coverage.items_excluded,
                    },
                ))
            
            # Financial terms chunk
            if coverage.financial_terms.deductible > 0 or coverage.financial_terms.coverage_cap:
                financial_text = self._build_financial_text(coverage)
                chunks.append(DocumentChunk(
                    text=financial_text,
                    chunk_type=ChunkType.FINANCIAL_TERMS,
                    policy_id=policy_id,
                    category=coverage.category,
                    metadata={
                        "deductible": coverage.financial_terms.deductible,
                        "cap": coverage.financial_terms.coverage_cap,
                    },
                ))
        
        # 3. Client obligations chunks
        if policy.client_obligations.mandatory_actions:
            for action in policy.client_obligations.mandatory_actions:
                action_text = f"Client obligation: {action.action}. Condition: {action.condition}."
                if action.penalty_for_breach:
                    action_text += f" Penalty for breach: {action.penalty_for_breach}."
                
                chunks.append(DocumentChunk(
                    text=action_text,
                    chunk_type=ChunkType.CLIENT_OBLIGATION,
                    policy_id=policy_id,
                    metadata={
                        "action": action.action,
                        "condition": action.condition,
                    },
                ))
        
        if policy.client_obligations.restrictions:
            restrictions_text = "Policy restrictions: " + "; ".join(policy.client_obligations.restrictions)
            chunks.append(DocumentChunk(
                text=restrictions_text,
                chunk_type=ChunkType.CLIENT_OBLIGATION,
                policy_id=policy_id,
                metadata={"type": "restrictions"},
            ))
        
        # 4. Service network chunk
        if policy.service_network:
            network_text = self._build_network_text(policy.service_network)
            chunks.append(DocumentChunk(
                text=network_text,
                chunk_type=ChunkType.SERVICE_NETWORK,
                policy_id=policy_id,
                metadata={
                    "network_type": policy.service_network.network_type.value,
                    "suppliers_count": len(policy.service_network.approved_suppliers),
                },
            ))
        
        # Generate embeddings and add to store
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.embed_many(texts)
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        self.vector_store.add_many(chunks)
        
        logger.info(f"Vectorized policy {policy_id}: {len(chunks)} chunks created")
        return len(chunks)
    
    def vectorize_raw_text(
        self,
        raw_text: str,
        policy_id: str,
        chunk_size: int = 2500,  # PAGE-LEVEL: Increased for Gemini's large context
        chunk_overlap: int = 500,  # More overlap to capture cross-paragraph exclusions
        page_breaks: Optional[list[int]] = None,  # Character positions of page breaks
        use_llm_classification: bool = True,  # NEW: Use Gemini for classification
    ) -> int:
        """
        Vectorize raw text with smart chunking and auto-classification.
        
        OPTIMIZED FOR GEMINI:
        - Page-level chunks (2500 chars) instead of tiny sentences
        - LLM-based classification replaces brittle regex
        - Preserves page numbers for citations
        
        Features:
        - Preserves page numbers for citations
        - Auto-classifies chunks as exclusion/inclusion/definition
        - Detects section titles
        - LLM-based classification (when enabled)
        
        Args:
            raw_text: Full text content of the policy
            policy_id: Policy ID to associate chunks with
            chunk_size: Target size of each chunk (2500 for page-level)
            chunk_overlap: Overlap between chunks for context continuity
            page_breaks: Character positions where pages break (for page numbers)
            use_llm_classification: Use Gemini to classify chunks (more accurate)
            
        Returns:
            Number of chunks created
        """
        chunks = []
        
        # Smart paragraph detection - try double newline first, fall back to single
        paragraphs = raw_text.split('\n\n')
        
        # If paragraphs are too long (avg > 1500 chars), split on single newlines
        if paragraphs:
            avg_len = sum(len(p) for p in paragraphs) / len(paragraphs)
            if avg_len > 1500:
                # Split on single newlines and group short lines
                lines = raw_text.split('\n')
                paragraphs = []
                current_para = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_para:
                            paragraphs.append(' '.join(current_para))
                            current_para = []
                    elif len(line) < 60 and line.isupper():
                        # Likely a header - start new paragraph
                        if current_para:
                            paragraphs.append(' '.join(current_para))
                            current_para = []
                        paragraphs.append(line)
                    else:
                        current_para.append(line)
                        # If current paragraph is getting long, split it
                        if len(' '.join(current_para)) > 800:
                            paragraphs.append(' '.join(current_para))
                            current_para = []
                
                if current_para:
                    paragraphs.append(' '.join(current_para))
        
        current_chunk = ""
        chunk_count = 0
        current_position = 0
        current_section = None
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                current_position += 2  # Account for \n\n
                continue
            
            # Detect section titles (ALL CAPS or ends with colon)
            if self._is_section_title(para):
                current_section = para.replace(':', '').strip()
                
            # If adding this paragraph would exceed chunk_size, save current chunk
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                # Calculate page number
                page_num = self._get_page_number(current_position, page_breaks)
                
                # Auto-classify the chunk
                chunk_type = self._classify_chunk_type(current_chunk)
                
                # Include section title in the chunk text for better embeddings
                chunk_text = current_chunk.strip()
                if current_section and current_section not in chunk_text:
                    chunk_text = f"[{current_section}]\n{chunk_text}"
                
                chunks.append(DocumentChunk(
                    text=chunk_text,
                    chunk_type=chunk_type,
                    policy_id=policy_id,
                    page_number=page_num,
                    section_title=current_section,
                    metadata={
                        "chunk_index": chunk_count,
                        "char_start": current_position - len(current_chunk),
                        "char_end": current_position,
                    },
                ))
                chunk_count += 1
                
                # Keep overlap from end of current chunk
                overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para
            
            current_position += len(para) + 2
        
        # Don't forget the last chunk
        if current_chunk.strip():
            page_num = self._get_page_number(current_position, page_breaks)
            chunk_type = self._classify_chunk_type(current_chunk)
            
            # Include section title in the chunk text for better embeddings
            chunk_text = current_chunk.strip()
            if current_section and current_section not in chunk_text:
                chunk_text = f"[{current_section}]\n{chunk_text}"
            
            chunks.append(DocumentChunk(
                text=chunk_text,
                chunk_type=chunk_type,
                policy_id=policy_id,
                page_number=page_num,
                section_title=current_section,
                metadata={"chunk_index": chunk_count},
            ))
        
        if not chunks:
            logger.warning(f"No chunks created from raw text for {policy_id}")
            return 0
        
        # LLM-based classification (more accurate than keywords)
        if use_llm_classification and len(chunks) <= 50:
            # Batch classification for small-medium documents
            logger.info(f"Running LLM classification on {len(chunks)} chunks...")
            chunks = self._classify_chunks_batch(chunks)
        elif use_llm_classification:
            # For large documents, classify in batches of 20
            logger.info(f"Running LLM classification on {len(chunks)} chunks (batched)...")
            for i in range(0, len(chunks), 20):
                batch = chunks[i:i+20]
                self._classify_chunks_batch(batch)
        
        # Generate embeddings and add to store
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.embed_many(texts)
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        self.vector_store.add_many(chunks)
        
        # Log classification stats
        type_counts = {}
        for chunk in chunks:
            t = chunk.chunk_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        
        logger.info(f"Vectorized raw text for {policy_id}: {len(chunks)} chunks")
        logger.info(f"  Classification: {type_counts}")
        
        return len(chunks)
    
    def _is_section_title(self, text: str) -> bool:
        """Detect if text is likely a section title."""
        text = text.strip()
        if not text:
            return False
        
        # Section titles should be SHORT (max 100 chars)
        if len(text) > 100:
            return False
        
        # All caps (at least 2 words, max 10 words)
        words = text.split()
        if text.isupper() and 2 <= len(words) <= 10:
            return True
        
        # Ends with colon (max 50 chars)
        if text.endswith(':') and len(text) <= 50:
            return True
        
        # Numbered section (e.g., "1. DEFINITIONS") - first 3 chars
        if len(text) <= 50 and text[0].isdigit() and '.' in text[:5]:
            return True
        
        # Common section headers
        section_patterns = [
            "coverage", "exclusion", "definition", "limit",
            "conditions", "obligation", "section", "part",
        ]
        text_lower = text.lower()
        if len(text) <= 50 and any(p in text_lower for p in section_patterns):
            return True
        
        return False
    
    def _get_page_number(
        self, 
        position: int, 
        page_breaks: Optional[list[int]]
    ) -> Optional[int]:
        """Calculate page number from character position."""
        if not page_breaks:
            # Estimate based on ~3000 chars per page
            return (position // 3000) + 1
        
        page = 1
        for break_pos in page_breaks:
            if position > break_pos:
                page += 1
            else:
                break
        return page
    
    def _classify_chunk_type(self, text: str) -> ChunkType:
        """
        Auto-classify a chunk based on its content (keyword-based fallback).
        
        This enables targeted retrieval in the reasoning loop.
        """
        text_lower = text.lower()
        
        # Exclusion indicators (highest priority - for guardrail)
        exclusion_keywords = [
            "not cover", "does not cover", "will not cover",
            "exclud", "exception", "not include", "shall not",
            "will not pay", "is not payable", "no coverage",
            "not applicable", "does not apply",
        ]
        if any(kw in text_lower for kw in exclusion_keywords):
            return ChunkType.EXCLUSION
        
        # Definition indicators
        definition_keywords = [
            "means", "defined as", "definition", "refers to",
            "is defined", "shall mean", "the term",
        ]
        if any(kw in text_lower for kw in definition_keywords):
            return ChunkType.DEFINITION
        
        # Limitation/financial indicators
        limitation_keywords = [
            "limit", "maximum", "cap", "deductible", 
            "not exceed", "up to", "subject to",
        ]
        if any(kw in text_lower for kw in limitation_keywords):
            return ChunkType.LIMITATION
        
        # Coverage/inclusion indicators
        inclusion_keywords = [
            "we will pay", "coverage include", "covered",
            "we cover", "this coverage", "provides coverage",
            "entitled to", "we agree to",
        ]
        if any(kw in text_lower for kw in inclusion_keywords):
            return ChunkType.INCLUSION
        
        # Procedure indicators
        procedure_keywords = [
            "must", "shall", "required", "notify", "report",
            "claim", "process", "submit", "within",
        ]
        if any(kw in text_lower for kw in procedure_keywords):
            return ChunkType.PROCEDURE
        
        return ChunkType.RAW_TEXT
    
    def _classify_with_llm(self, text: str) -> ChunkType:
        """
        Use Gemini to classify chunk type (more accurate than keywords).
        
        This is the "labelling pass" during ingestion - cheap with Gemini Flash.
        """
        try:
            from app.services.llm_service import get_llm
            from app.core.config import settings
            
            llm = get_llm()
            
            # Truncate long text for classification
            sample = text[:2000] if len(text) > 2000 else text
            
            prompt = f"""Read this insurance policy text chunk and classify it into ONE of these categories:

EXCLUSION - Contains language that explicitly denies or limits coverage (e.g., "we do not cover", "excluded", "not payable")
INCLUSION - Contains language that confirms coverage (e.g., "we will pay", "covered", "we cover")
DEFINITION - Contains definitions of terms (e.g., "means", "defined as", "the term X refers to")
LIMITATION - Contains financial limits, caps, or deductibles (e.g., "maximum of", "subject to a limit", "deductible")
PROCEDURE - Contains claims procedures or requirements (e.g., "you must notify", "submit within")
GENERAL - General information that doesn't fit the above categories

Respond with ONLY the category name (one word).

Text chunk:
\"\"\"
{sample}
\"\"\"

Category:"""

            response = llm.generate(prompt)
            category = response.strip().upper()
            
            # Map to ChunkType
            mapping = {
                "EXCLUSION": ChunkType.EXCLUSION,
                "INCLUSION": ChunkType.INCLUSION,
                "DEFINITION": ChunkType.DEFINITION,
                "LIMITATION": ChunkType.LIMITATION,
                "PROCEDURE": ChunkType.PROCEDURE,
                "GENERAL": ChunkType.RAW_TEXT,
            }
            
            return mapping.get(category, ChunkType.RAW_TEXT)
            
        except Exception as e:
            logger.warning(f"LLM classification failed, using keyword fallback: {e}")
            return self._classify_chunk_type(text)
    
    def _classify_chunks_batch(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """
        Classify multiple chunks using LLM (batch for efficiency).
        
        Uses Gemini Flash for cheap, accurate classification during ingestion.
        """
        try:
            from app.services.llm_service import get_llm
            
            llm = get_llm()
            
            # Build batch prompt
            samples = []
            for i, chunk in enumerate(chunks):
                sample = chunk.text[:1500] if len(chunk.text) > 1500 else chunk.text
                samples.append(f"[CHUNK {i}]\n{sample}")
            
            prompt = f"""Classify each of these insurance policy text chunks into ONE category per chunk.

Categories:
- EXCLUSION: Explicitly denies/limits coverage ("we do not cover", "excluded")
- INCLUSION: Confirms coverage ("we will pay", "covered")
- DEFINITION: Defines terms ("means", "defined as")
- LIMITATION: Financial limits/caps ("maximum of", "deductible")
- PROCEDURE: Claims procedures ("you must notify")
- GENERAL: Everything else

For each chunk, respond with just the chunk number and category, like:
0: EXCLUSION
1: INCLUSION
2: GENERAL

Chunks to classify:

{chr(10).join(samples)}

Classifications:"""

            response = llm.generate(prompt)
            
            # Parse response
            mapping = {
                "EXCLUSION": ChunkType.EXCLUSION,
                "INCLUSION": ChunkType.INCLUSION,
                "DEFINITION": ChunkType.DEFINITION,
                "LIMITATION": ChunkType.LIMITATION,
                "PROCEDURE": ChunkType.PROCEDURE,
                "GENERAL": ChunkType.RAW_TEXT,
            }
            
            for line in response.strip().split('\n'):
                line = line.strip()
                if ':' in line:
                    try:
                        idx_str, category = line.split(':', 1)
                        idx = int(idx_str.strip())
                        category = category.strip().upper()
                        
                        if 0 <= idx < len(chunks) and category in mapping:
                            chunks[idx].chunk_type = mapping[category]
                    except (ValueError, IndexError):
                        continue
            
            return chunks
            
        except Exception as e:
            logger.warning(f"Batch LLM classification failed, using keyword fallback: {e}")
            for chunk in chunks:
                chunk.chunk_type = self._classify_chunk_type(chunk.text)
            return chunks
    
    def search(
        self,
        query: str,
        policy_id: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[VectorSearchResult]:
        """
        Search for relevant policy chunks.
        
        Args:
            query: Natural language query
            policy_id: Optional policy ID to filter by
            top_k: Number of results
            min_score: Minimum similarity threshold
            
        Returns:
            List of search results
        """
        query_embedding = self.embedding_service.embed(query)
        
        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            policy_id=policy_id,
            min_score=min_score,
        )
    
    def search_coverage(
        self,
        query: str,
        policy_id: str,
        include_exclusions: bool = True,
        top_k: int = 5,
    ) -> dict:
        """
        Search specifically for coverage-related information.
        
        Args:
            query: Natural language query about coverage
            policy_id: Policy ID to search in
            include_exclusions: Whether to include exclusion chunks
            top_k: Number of results per category
            
        Returns:
            Dict with inclusions and exclusions results
        """
        query_embedding = self.embedding_service.embed(query)
        
        # Search inclusions
        inclusions = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            policy_id=policy_id,
            chunk_type=ChunkType.COVERAGE_INCLUSION,
        )
        
        results = {
            "inclusions": inclusions,
            "exclusions": [],
        }
        
        if include_exclusions:
            exclusions = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                policy_id=policy_id,
                chunk_type=ChunkType.COVERAGE_EXCLUSION,
            )
            results["exclusions"] = exclusions
        
        return results
    
    def remove_policy(self, policy_id: str) -> int:
        """
        Remove all chunks for a policy.
        
        Args:
            policy_id: Policy ID to remove
            
        Returns:
            Number of chunks removed
        """
        return self.vector_store.delete_by_policy(policy_id)
    
    def get_stats(self) -> dict:
        """Get vectorizer statistics."""
        store_stats = self.vector_store.get_stats() if hasattr(self.vector_store, 'get_stats') else {}
        return {
            "embedding_dim": self.embedding_service.embedding_dim,
            **store_stats,
        }
    
    # Text building helpers
    
    def _build_meta_text(self, policy: PolicyDocument) -> str:
        """Build searchable text for policy metadata."""
        meta = policy.policy_meta
        return (
            f"Insurance policy {meta.policy_id} from {meta.provider_name}. "
            f"Policy type: {meta.policy_type}. Status: {meta.status.value}. "
            f"Valid until {meta.validity_period.end_date_calculated.strftime('%Y-%m-%d')}."
        )
    
    def _build_inclusion_text(self, coverage) -> str:
        """Build searchable text for coverage inclusions."""
        items_str = ", ".join(coverage.items_included)
        text = f"{coverage.category} coverage includes: {items_str}."
        
        if coverage.specific_limitations:
            text += f" Limitations: {coverage.specific_limitations}"
        
        return text
    
    def _build_exclusion_text(self, coverage) -> str:
        """Build searchable text for coverage exclusions."""
        items_str = ", ".join(coverage.items_excluded)
        return f"{coverage.category} coverage excludes: {items_str}. These items are NOT covered."
    
    def _build_financial_text(self, coverage) -> str:
        """Build searchable text for financial terms."""
        text = f"{coverage.category} financial terms: "
        
        if coverage.financial_terms.deductible > 0:
            text += f"Deductible is {coverage.financial_terms.deductible} NIS. "
        else:
            text += "No deductible required. "
        
        if coverage.financial_terms.coverage_cap:
            cap = coverage.financial_terms.coverage_cap
            if isinstance(cap, str):
                text += f"Coverage cap: {cap}."
            else:
                text += f"Coverage cap: {cap} NIS."
        
        return text
    
    def _build_network_text(self, network) -> str:
        """Build searchable text for service network."""
        text = f"Service network type: {network.network_type.value}. "
        
        if network.approved_suppliers:
            suppliers = [s.name for s in network.approved_suppliers]
            text += f"Approved suppliers: {', '.join(suppliers)}. "
        
        if network.access_method:
            text += f"Access method: {network.access_method}"
        
        return text

