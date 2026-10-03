"""Sparse Lexical Search Engine (BM25Plus) with ACL Filtering and Persistence."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Plus

from app.core.config import settings
from app.services.chunking import ChildChunk

logger = logging.getLogger("rag.services.bm25")


class BM25Service:
    """High-speed inverted sparse lexical index capturing exact domain nomenclature and codes."""

    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path or settings.BM25_PERSIST_PATH
        self.corpus_chunks: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Plus] = None

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase lexical terms while preserving technical identifiers."""
        # Match alphanumeric words, including internal hyphens and underscores (e.g., hr_policy_2026, ERR-404)
        tokens = re.findall(r"\b[\w\-.]+\b", text.lower())
        return tokens

    def index_chunks(self, chunks: List[ChildChunk]) -> int:
        """Add child chunks to BM25 index and rebuild frequency model."""
        if not chunks:
            return 0

        for chunk in chunks:
            payload = chunk.to_payload()
            self.corpus_chunks.append(payload)
            self.tokenized_corpus.append(self.tokenize(chunk.text))

        self.bm25 = BM25Plus(self.tokenized_corpus)
        logger.info(
            "BM25 index updated: %d total documents indexed.",
            len(self.corpus_chunks),
        )
        return len(chunks)

    def search_sparse(
        self,
        query: str,
        acl_groups: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Execute BM25 lexical keyword query with ACL filtering."""
        if not self.bm25 or not self.corpus_chunks:
            return []

        user_acls = acl_groups if acl_groups is not None else ["group_all"]
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores across all documents
        doc_scores = self.bm25.get_scores(query_tokens)
        query_set = set(query_tokens)

        # Pair scores with document payloads and filter by ACL and term presence
        scored_candidates = []
        for idx, score in enumerate(doc_scores):
            # Ensure document actually contains at least one query term
            doc_token_set = set(self.tokenized_corpus[idx])
            if not query_set.intersection(doc_token_set):
                continue

            doc_meta = self.corpus_chunks[idx]
            doc_acls = doc_meta.get("access_control_list", ["group_all"])

            # Verify RBAC authorization
            if user_acls and not any(acl in user_acls for acl in doc_acls):
                continue

            scored_candidates.append(
                {
                    "child_id": doc_meta.get("child_id"),
                    "parent_id": doc_meta.get("parent_id"),
                    "doc_id": doc_meta.get("doc_id"),
                    "section_header": doc_meta.get("section_header"),
                    "text": doc_meta.get("text"),
                    "parent_text": doc_meta.get("parent_text"),
                    "score": float(score),
                    "metadata": doc_meta,
                }
            )

        # Sort descending by score and truncate to limit
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:limit]

    def save(self, filepath: Optional[str] = None) -> None:
        """Persist BM25 corpus and metadata state to disk."""
        target = filepath or self.persist_path
        data = {
            "corpus_chunks": self.corpus_chunks,
        }
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info("Saved BM25 state with %d chunks to %s", len(self.corpus_chunks), target)

    def load(self, filepath: Optional[str] = None) -> bool:
        """Restore BM25 corpus from disk and re-initialize model."""
        target = filepath or self.persist_path
        if not os.path.exists(target):
            return False

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.corpus_chunks = data.get("corpus_chunks", [])
            self.tokenized_corpus = [
                self.tokenize(c.get("text", "")) for c in self.corpus_chunks
            ]
            if self.tokenized_corpus:
                self.bm25 = BM25Plus(self.tokenized_corpus)
            logger.info("Restored BM25 state with %d chunks from %s", len(self.corpus_chunks), target)
            return True
        except Exception as exc:
            logger.warning("Failed to restore BM25 state from %s: %s", target, exc)
            return False
