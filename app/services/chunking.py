"""Hierarchical Parent-Child Chunking Engine with Token Tracking."""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import tiktoken

from app.core.config import settings
from app.services.parser import DocumentSection


@dataclass
class ChildChunk:
    """Indexed child chunk optimized for dense vector and lexical BM25 retrieval."""

    child_id: str
    parent_id: str
    doc_id: str
    section_header: str
    text: str
    token_count: int
    parent_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convert chunk into storage payload for vector databases and BM25."""
        payload = {
            "child_id": self.child_id,
            "parent_id": self.parent_id,
            "doc_id": self.doc_id,
            "section_header": self.section_header,
            "text": self.text,
            "token_count": self.token_count,
            "parent_text": self.parent_text,
        }
        payload.update(self.metadata)
        return payload


@dataclass
class ParentChunk:
    """Full-context parent chunk passed to the LLM to preserve narrative coherence."""

    parent_id: str
    doc_id: str
    section_header: str
    text: str
    token_count: int
    children: List[ChildChunk] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HierarchicalChunker:
    """Splits document sections into parent context blocks and overlapping child search units."""

    def __init__(
        self,
        parent_chunk_size: Optional[int] = None,
        child_chunk_size: Optional[int] = None,
        child_chunk_overlap: Optional[int] = None,
        encoding_name: str = "cl100k_base",
    ):
        self.parent_chunk_size = parent_chunk_size or settings.PARENT_CHUNK_SIZE
        self.child_chunk_size = child_chunk_size or settings.CHILD_CHUNK_SIZE
        self.child_chunk_overlap = (
            child_chunk_overlap or settings.CHILD_CHUNK_OVERLAP
        )
        try:
            self.tokenizer = tiktoken.get_encoding(encoding_name)
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Calculate token length of given text."""
        return len(self.tokenizer.encode(text, disallowed_special=()))

    def chunk_section(
        self, section: DocumentSection, global_parent_idx: int = 0
    ) -> List[ParentChunk]:
        """Process a DocumentSection into parent chunks and contained child chunks."""
        text = section.content.strip()
        if not text:
            return []

        tokens = self.tokenizer.encode(text, disallowed_special=())
        total_tokens = len(tokens)

        parent_chunks: List[ParentChunk] = []

        if total_tokens <= self.parent_chunk_size:
            # Section fits comfortably within single parent chunk
            p_id = self._generate_id(
                "p", section.doc_id, global_parent_idx, text[:64]
            )
            parent = ParentChunk(
                parent_id=p_id,
                doc_id=section.doc_id,
                section_header=section.section_header,
                text=text,
                token_count=total_tokens,
                metadata=section.metadata.copy(),
            )
            parent.children = self._create_child_chunks(parent, tokens)
            parent_chunks.append(parent)
        else:
            # Split section across multiple parent chunks with 10% overlap
            parent_overlap = int(self.parent_chunk_size * 0.1)
            step = max(1, self.parent_chunk_size - parent_overlap)

            sub_idx = 0
            for start in range(0, total_tokens, step):
                end = min(start + self.parent_chunk_size, total_tokens)
                slice_tokens = tokens[start:end]
                parent_text = self.tokenizer.decode(slice_tokens)

                p_id = self._generate_id(
                    "p",
                    section.doc_id,
                    global_parent_idx + sub_idx,
                    parent_text[:64],
                )
                parent = ParentChunk(
                    parent_id=p_id,
                    doc_id=section.doc_id,
                    section_header=section.section_header,
                    text=parent_text,
                    token_count=len(slice_tokens),
                    metadata=section.metadata.copy(),
                )
                parent.children = self._create_child_chunks(
                    parent, slice_tokens, sub_idx
                )
                parent_chunks.append(parent)
                sub_idx += 1

                if end == total_tokens:
                    break

        return parent_chunks

    def _create_child_chunks(
        self,
        parent: ParentChunk,
        parent_tokens: List[int],
        parent_sub_idx: int = 0,
    ) -> List[ChildChunk]:
        """Divide parent chunk token stream into overlapping child units."""
        total_tokens = len(parent_tokens)
        children: List[ChildChunk] = []

        if total_tokens <= self.child_chunk_size:
            c_id = self._generate_id(
                "c", parent.parent_id, 0, parent.text[:64]
            )
            child = ChildChunk(
                child_id=c_id,
                parent_id=parent.parent_id,
                doc_id=parent.doc_id,
                section_header=parent.section_header,
                text=parent.text,
                token_count=total_tokens,
                parent_text=parent.text,
                metadata=parent.metadata.copy(),
            )
            children.append(child)
            return children

        step = max(1, self.child_chunk_size - self.child_chunk_overlap)
        child_idx = 0

        for start in range(0, total_tokens, step):
            end = min(start + self.child_chunk_size, total_tokens)
            slice_tokens = parent_tokens[start:end]
            child_text = self.tokenizer.decode(slice_tokens)

            c_id = self._generate_id(
                "c",
                parent.parent_id,
                child_idx,
                child_text[:64],
            )
            child = ChildChunk(
                child_id=c_id,
                parent_id=parent.parent_id,
                doc_id=parent.doc_id,
                section_header=parent.section_header,
                text=child_text,
                token_count=len(slice_tokens),
                parent_text=parent.text,
                metadata=parent.metadata.copy(),
            )
            children.append(child)
            child_idx += 1

            if end == total_tokens:
                break

        return children

    def chunk_document(
        self, sections: List[DocumentSection]
    ) -> List[ParentChunk]:
        """Process all sections of a document into a flat hierarchy of ParentChunks with linked children."""
        all_parents: List[ParentChunk] = []
        for idx, section in enumerate(sections):
            parent_chunks = self.chunk_section(section, global_parent_idx=idx)
            all_parents.extend(parent_chunks)
        return all_parents

    def extract_all_child_chunks(
        self, parent_chunks: List[ParentChunk]
    ) -> List[ChildChunk]:
        """Convenience method to flatten all child chunks ready for vector/BM25 indexing."""
        all_children: List[ChildChunk] = []
        for parent in parent_chunks:
            all_children.extend(parent.children)
        return all_children

    @staticmethod
    def _generate_id(
        prefix: str, parent_key: str, index: int, sample_text: str
    ) -> str:
        """Create deterministic, collision-resistant identifier."""
        raw = f"{prefix}:{parent_key}:{index}:{sample_text}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{digest}"
