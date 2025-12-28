"""
Smart text chunking for RAG.

Provides multiple chunking strategies optimized for insurance documents.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import hashlib


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"  # Fixed character count
    SENTENCE = "sentence"  # Sentence boundaries
    PARAGRAPH = "paragraph"  # Paragraph boundaries
    SEMANTIC = "semantic"  # Section-aware (headers, lists)
    HYBRID = "hybrid"  # Combination of strategies


@dataclass
class Chunk:
    """A text chunk with metadata."""
    
    id: str
    text: str
    index: int  # Position in document
    start_char: int  # Character offset
    end_char: int
    metadata: dict = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        """Character length of chunk."""
        return len(self.text)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "index": self.index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "metadata": self.metadata,
        }


class SmartChunker:
    """
    Smart text chunking with multiple strategies.
    
    Optimized for insurance policy documents with section-aware chunking.
    """
    
    # Insurance-specific section patterns
    SECTION_PATTERNS = [
        r"^#{1,6}\s+",  # Markdown headers
        r"^[A-Z][A-Z\s]+:$",  # ALL CAPS headers
        r"^\d+\.\s+[A-Z]",  # Numbered sections
        r"^(?:Section|Article|Part)\s+\d+",  # Formal sections
        r"^(?:COVERAGE|EXCLUSIONS?|LIMITATIONS?|DEFINITIONS?)",  # Policy sections
    ]
    
    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
    
    # Paragraph pattern
    PARAGRAPH_PATTERN = re.compile(r'\n\s*\n')
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
        min_chunk_size: int = 100,
    ):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between consecutive chunks
            strategy: Chunking strategy to use
            min_chunk_size: Minimum chunk size (smaller chunks merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size
        
        # Compile section patterns
        self._section_re = re.compile(
            '|'.join(f'({p})' for p in self.SECTION_PATTERNS),
            re.MULTILINE | re.IGNORECASE
        )
    
    def chunk(
        self,
        text: str,
        doc_id: str = "",
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Chunk text using the configured strategy.
        
        Args:
            text: Text to chunk
            doc_id: Document ID for chunk IDs
            metadata: Additional metadata for all chunks
            
        Returns:
            List of chunks
        """
        if not text.strip():
            return []
        
        metadata = metadata or {}
        
        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed_size(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_by_sentence(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_by_paragraph(text, doc_id, metadata)
        elif self.strategy == ChunkingStrategy.SEMANTIC:
            return self._chunk_semantic(text, doc_id, metadata)
        else:  # HYBRID
            return self._chunk_hybrid(text, doc_id, metadata)
    
    def _generate_chunk_id(self, doc_id: str, text: str, index: int) -> str:
        """Generate unique chunk ID."""
        content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"{doc_id}_chunk_{index}_{content_hash}"
    
    def _chunk_fixed_size(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """Chunk by fixed character count with overlap."""
        chunks = []
        start = 0
        index = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at word boundary
            if end < len(text):
                space_pos = text.rfind(' ', start, end)
                if space_pos > start + self.min_chunk_size:
                    end = space_pos + 1
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append(Chunk(
                    id=self._generate_chunk_id(doc_id, chunk_text, index),
                    text=chunk_text,
                    index=index,
                    start_char=start,
                    end_char=end,
                    metadata={**metadata, "strategy": "fixed_size"},
                ))
                index += 1
            
            start = end - self.chunk_overlap
            if start >= len(text) - self.min_chunk_size:
                break
        
        return chunks
    
    def _chunk_by_sentence(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """Chunk by sentence boundaries."""
        sentences = self.SENTENCE_ENDINGS.split(text)
        chunks = []
        current_chunk = []
        current_length = 0
        start_char = 0
        index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if current_length + len(sentence) > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append(Chunk(
                    id=self._generate_chunk_id(doc_id, chunk_text, index),
                    text=chunk_text,
                    index=index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={**metadata, "strategy": "sentence"},
                ))
                index += 1
                start_char += len(chunk_text) + 1
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += len(sentence) + 1
        
        # Save remaining
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(Chunk(
                id=self._generate_chunk_id(doc_id, chunk_text, index),
                text=chunk_text,
                index=index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={**metadata, "strategy": "sentence"},
            ))
        
        return chunks
    
    def _chunk_by_paragraph(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """Chunk by paragraph boundaries."""
        paragraphs = self.PARAGRAPH_PATTERN.split(text)
        chunks = []
        current_chunk = []
        current_length = 0
        start_char = 0
        index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if current_length + len(para) > self.chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(Chunk(
                    id=self._generate_chunk_id(doc_id, chunk_text, index),
                    text=chunk_text,
                    index=index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={**metadata, "strategy": "paragraph"},
                ))
                index += 1
                start_char += len(chunk_text) + 2
                current_chunk = []
                current_length = 0
            
            current_chunk.append(para)
            current_length += len(para) + 2
        
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(Chunk(
                id=self._generate_chunk_id(doc_id, chunk_text, index),
                text=chunk_text,
                index=index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={**metadata, "strategy": "paragraph"},
            ))
        
        return chunks
    
    def _chunk_semantic(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """Chunk by semantic sections (headers, policy sections)."""
        # Find section boundaries
        sections = []
        last_end = 0
        
        for match in self._section_re.finditer(text):
            if match.start() > last_end:
                sections.append((last_end, match.start()))
            last_end = match.start()
        
        if last_end < len(text):
            sections.append((last_end, len(text)))
        
        # If no sections found, fall back to paragraph chunking
        if len(sections) <= 1:
            return self._chunk_by_paragraph(text, doc_id, metadata)
        
        chunks = []
        index = 0
        
        for start, end in sections:
            section_text = text[start:end].strip()
            
            if len(section_text) > self.chunk_size:
                # Sub-chunk large sections
                sub_chunks = self._chunk_fixed_size(
                    section_text,
                    f"{doc_id}_sec{index}",
                    {**metadata, "section_index": index},
                )
                for sub in sub_chunks:
                    sub.start_char += start
                    sub.end_char += start
                    sub.metadata["strategy"] = "semantic"
                chunks.extend(sub_chunks)
            elif section_text:
                chunks.append(Chunk(
                    id=self._generate_chunk_id(doc_id, section_text, index),
                    text=section_text,
                    index=index,
                    start_char=start,
                    end_char=end,
                    metadata={**metadata, "strategy": "semantic"},
                ))
            
            index += 1
        
        return chunks
    
    def _chunk_hybrid(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """
        Hybrid chunking: semantic sections + sentence boundaries.
        
        Best for insurance documents.
        """
        # First try semantic chunking
        semantic_chunks = self._chunk_semantic(text, doc_id, metadata)
        
        # Post-process: merge small chunks, split large ones at sentences
        result = []
        buffer = []
        buffer_length = 0
        
        for chunk in semantic_chunks:
            if chunk.length < self.min_chunk_size:
                buffer.append(chunk)
                buffer_length += chunk.length
                
                if buffer_length >= self.chunk_size:
                    # Merge buffer
                    merged_text = ' '.join(c.text for c in buffer)
                    result.append(Chunk(
                        id=self._generate_chunk_id(doc_id, merged_text, len(result)),
                        text=merged_text,
                        index=len(result),
                        start_char=buffer[0].start_char,
                        end_char=buffer[-1].end_char,
                        metadata={**metadata, "strategy": "hybrid", "merged": True},
                    ))
                    buffer = []
                    buffer_length = 0
            else:
                # Flush buffer first
                if buffer:
                    merged_text = ' '.join(c.text for c in buffer)
                    result.append(Chunk(
                        id=self._generate_chunk_id(doc_id, merged_text, len(result)),
                        text=merged_text,
                        index=len(result),
                        start_char=buffer[0].start_char,
                        end_char=buffer[-1].end_char,
                        metadata={**metadata, "strategy": "hybrid", "merged": True},
                    ))
                    buffer = []
                    buffer_length = 0
                
                chunk.metadata["strategy"] = "hybrid"
                chunk.index = len(result)
                result.append(chunk)
        
        # Flush remaining buffer
        if buffer:
            merged_text = ' '.join(c.text for c in buffer)
            result.append(Chunk(
                id=self._generate_chunk_id(doc_id, merged_text, len(result)),
                text=merged_text,
                index=len(result),
                start_char=buffer[0].start_char,
                end_char=buffer[-1].end_char,
                metadata={**metadata, "strategy": "hybrid", "merged": True},
            ))
        
        return result

