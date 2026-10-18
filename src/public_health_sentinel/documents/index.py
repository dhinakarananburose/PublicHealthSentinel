"""Persistent lightweight vector index manager for PublicHealthSentinel Phase 6B.1.

Manages persistent NumPy .npz vector indexes and metadata under data/index/.
Provides:
- L2-normalized dense vector persistence with chunk and document mapping
- Dot-product cosine similarity search with optional filtering
- Atomic file writes to prevent index corruption
- Incompatible embedding model detection and prevention
- Index rebuilding directly from database DocumentChunkModel records
- Thread-safe operational state inspection
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentChunkModel
from public_health_sentinel.documents.embeddings import EmbeddingService

logger = logging.getLogger("public_health_sentinel.documents.index")

INDEX_VERSION = "1.0.0"
INDEX_NPZ_FILENAME = "evidence_vector_index.npz"
INDEX_META_FILENAME = "evidence_vector_index_meta.json"


class VectorIndexError(Exception):
    """Base exception for vector index operations."""
    pass


class IncompatibleIndexModelError(VectorIndexError):
    """Raised when attempting to add or query embeddings with an incompatible model."""
    pass


class CorruptedIndexError(VectorIndexError):
    """Raised when index files exist but cannot be parsed or are structurally invalid."""
    pass


class VectorIndexManager:
    """Persistent NumPy-based vector index for semantic evidence passage retrieval."""

    def __init__(
        self,
        index_dir: Optional[Union[str, Path]] = None,
        expected_dim: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> None:
        config = get_config()
        self._index_dir = Path(index_dir) if index_dir else config.data_index_dir

        if model_name is None:
            from public_health_sentinel.documents.embeddings import get_embedding_service
            emb_svc = get_embedding_service()
            self._configured_model = emb_svc.model_name
            self._expected_dim = expected_dim or emb_svc.dimension
        else:
            self._configured_model = model_name
            self._expected_dim = expected_dim or config.embedding_dimension

        self._npz_path = self._index_dir / INDEX_NPZ_FILENAME
        self._meta_path = self._index_dir / INDEX_META_FILENAME

        # In-memory index structures
        self._vectors: np.ndarray = np.empty((0, self._expected_dim), dtype=np.float32)
        self._chunk_ids: list[str] = []
        self._document_ids: list[str] = []
        self._active_model_name: str = self._configured_model
        self._last_updated: Optional[datetime] = None
        self._is_degraded: bool = False
        self._degraded_reason: Optional[str] = None

        # Load existing index on initialization if present
        self.load()

    @property
    def index_dir(self) -> Path:
        return self._index_dir

    @property
    def total_vectors(self) -> int:
        return len(self._chunk_ids)

    @property
    def chunk_ids(self) -> list[str]:
        return list(self._chunk_ids)

    @property
    def document_ids(self) -> list[str]:
        return list(self._document_ids)

    @property
    def active_model_name(self) -> str:
        return self._active_model_name

    @property
    def configured_model_name(self) -> str:
        return self._configured_model


    @property
    def dimension(self) -> int:
        return self._expected_dim

    @property
    def is_degraded(self) -> bool:
        return self._is_degraded

    @property
    def degraded_reason(self) -> Optional[str]:
        return self._degraded_reason

    def load(self) -> bool:
        """Load index and metadata from disk if available.
        
        Returns:
            True if existing index was loaded successfully, False if index was initialized empty or degraded.
        """
        self._index_dir.mkdir(parents=True, exist_ok=True)

        npz_exists = self._npz_path.exists()
        meta_exists = self._meta_path.exists()

        if not npz_exists and not meta_exists:
            self._reset_empty(self._configured_model)
            self._is_degraded = False
            self._degraded_reason = None
            return False

        if npz_exists != meta_exists:
            self._reset_empty(self._configured_model)
            self._is_degraded = True
            self._degraded_reason = (
                f"Incomplete vector index on disk: npz_exists={npz_exists}, meta_exists={meta_exists}. "
                "Vector index rebuild is recommended."
            )
            logger.warning(self._degraded_reason)
            return False

        try:
            with open(self._meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            model_in_meta = meta.get("embedding_model", self._configured_model)
            dim_in_meta = int(meta.get("dimension", self._expected_dim))

            if dim_in_meta != self._expected_dim:
                self._reset_empty(self._configured_model)
                self._is_degraded = True
                self._degraded_reason = (
                    f"Index dimension mismatch: metadata recorded {dim_in_meta}-D, expected {self._expected_dim}-D. "
                    "Rebuilding vector index from database is required."
                )
                logger.warning(self._degraded_reason)
                return False

            with np.load(self._npz_path, allow_pickle=False) as data:
                vectors = data["vectors"].astype(np.float32)
                chunk_ids = [str(cid) for cid in data["chunk_ids"]]
                document_ids = [str(did) for did in data["document_ids"]]

            if len(vectors) != len(chunk_ids) or len(vectors) != len(document_ids):
                raise CorruptedIndexError("Vector count does not match chunk_ids or document_ids length.")

            if len(vectors) > 0 and vectors.shape[1] != self._expected_dim:
                raise CorruptedIndexError(
                    f"Vector shape mismatch: expected (_, {self._expected_dim}), got {vectors.shape}"
                )

            self._vectors = vectors
            self._chunk_ids = chunk_ids
            self._document_ids = document_ids
            self._active_model_name = model_in_meta
            updated_str = meta.get("updated_at")
            self._last_updated = datetime.fromisoformat(updated_str) if updated_str else None

            # Detect model mismatch with populated vectors
            if len(self._chunk_ids) > 0 and self._active_model_name != self._configured_model:
                self._is_degraded = True
                self._degraded_reason = (
                    f"Active index model '{self._active_model_name}' differs from configured model '{self._configured_model}'. "
                    "Index rebuild from database is recommended."
                )
                logger.warning(self._degraded_reason)
            else:
                self._is_degraded = False
                self._degraded_reason = None

            logger.info(
                "Loaded vector index from %s (%d vectors, model=%s)",
                self._npz_path,
                len(self._chunk_ids),
                self._active_model_name,
            )
            return True

        except Exception as exc:
            self._reset_empty(self._configured_model)
            self._is_degraded = True
            self._degraded_reason = f"Corrupted or incompatible vector index files on disk: {exc}. Rebuild required."
            logger.warning("Failed to load existing vector index: %s", self._degraded_reason)
            return False

    def _reset_empty(self, model_name: str) -> None:
        """Reset in-memory state to empty."""
        self._vectors = np.empty((0, self._expected_dim), dtype=np.float32)
        self._chunk_ids = []
        self._document_ids = []
        self._active_model_name = model_name
        self._last_updated = None

    def save(self) -> None:
        """Persist in-memory vectors and metadata atomically to disk."""
        self._index_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        self._last_updated = now

        meta = {
            "version": INDEX_VERSION,
            "embedding_model": self._active_model_name,
            "dimension": self._expected_dim,
            "total_vectors": len(self._chunk_ids),
            "updated_at": now.isoformat(),
        }

        temp_meta = self._index_dir / "temp_index_meta.json"
        temp_npz = self._index_dir / "temp_index.npz"

        try:
            # Atomic write metadata
            with open(temp_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            # Atomic write npz (use np.str_ so allow_pickle=False works safely without object arrays)
            np.savez_compressed(
                temp_npz,
                vectors=self._vectors,
                chunk_ids=np.array(self._chunk_ids, dtype=np.str_),
                document_ids=np.array(self._document_ids, dtype=np.str_),
            )

            # Atomic replace (works cross-platform on Windows and Linux)
            os.replace(temp_meta, self._meta_path)
            os.replace(temp_npz, self._npz_path)

            logger.info("Saved vector index (%d vectors) to %s", len(self._chunk_ids), self._npz_path)
        finally:
            if temp_meta.exists():
                try:
                    temp_meta.unlink()
                except OSError:
                    pass
            if temp_npz.exists():
                try:
                    temp_npz.unlink()
                except OSError:
                    pass

    def add_chunks(
        self,
        chunks: list[tuple[str, str, np.ndarray]],  # (chunk_id, document_id, vector)
        model_name: str,
    ) -> int:
        """Add or update chunk vectors in the persistent index.

        Args:
            chunks: List of tuples (chunk_id, document_id, vector).
            model_name: Identifier of embedding model used to generate vectors.

        Returns:
            Number of chunks indexed.

        Raises:
            IncompatibleIndexModelError: If model_name differs from existing populated index.
            VectorIndexError: If vectors have invalid dimensions or values.
        """
        if not chunks:
            return 0

        # Model compatibility check
        if len(self._chunk_ids) > 0 and model_name != self._active_model_name:
            raise IncompatibleIndexModelError(
                f"Cannot add vectors generated with model '{model_name}' to index configured with '{self._active_model_name}'."
            )

        if len(self._chunk_ids) == 0:
            self._active_model_name = model_name

        new_chunk_ids = []
        new_doc_ids = []
        new_vecs = []

        for cid, did, vec in chunks:
            if not isinstance(vec, np.ndarray):
                vec = np.asarray(vec, dtype=np.float32)
            else:
                vec = vec.astype(np.float32)

            if vec.shape != (self._expected_dim,):
                raise VectorIndexError(f"Vector for chunk {cid} has shape {vec.shape}, expected ({self._expected_dim},)")

            if np.isnan(vec).any() or np.isinf(vec).any():
                raise VectorIndexError(f"Vector for chunk {cid} contains NaN or Infinite values.")

            norm = np.linalg.norm(vec)
            if norm > 1e-8:
                vec = vec / norm

            new_chunk_ids.append(cid)
            new_doc_ids.append(did)
            new_vecs.append(vec)

        # Merge logic: if any chunk_id already exists, replace it; otherwise append
        existing_id_to_idx = {cid: idx for idx, cid in enumerate(self._chunk_ids)}
        update_indices = []
        append_indices = []

        for i, cid in enumerate(new_chunk_ids):
            if cid in existing_id_to_idx:
                update_indices.append((existing_id_to_idx[cid], i))
            else:
                append_indices.append(i)

        # Apply updates in-place
        for existing_idx, new_idx in update_indices:
            self._vectors[existing_idx] = new_vecs[new_idx]
            self._document_ids[existing_idx] = new_doc_ids[new_idx]

        # Apply appends
        if append_indices:
            append_vecs = np.vstack([new_vecs[i] for i in append_indices])
            append_cids = [new_chunk_ids[i] for i in append_indices]
            append_dids = [new_doc_ids[i] for i in append_indices]

            if len(self._chunk_ids) == 0:
                self._vectors = append_vecs
            else:
                self._vectors = np.vstack([self._vectors, append_vecs])
            self._chunk_ids.extend(append_cids)
            self._document_ids.extend(append_dids)

        self.save()
        return len(chunks)

    def remove_by_document_id(self, document_id: str) -> int:
        """Remove all chunks associated with a specific document.

        Returns:
            Number of chunks removed.
        """
        if len(self._chunk_ids) == 0:
            return 0

        keep_indices = [i for i, did in enumerate(self._document_ids) if did != document_id]
        removed_count = len(self._chunk_ids) - len(keep_indices)

        if removed_count == 0:
            return 0

        if len(keep_indices) == 0:
            self._reset_empty(self._active_model_name)
        else:
            self._vectors = self._vectors[keep_indices]
            self._chunk_ids = [self._chunk_ids[i] for i in keep_indices]
            self._document_ids = [self._document_ids[i] for i in keep_indices]

        self.save()
        return removed_count

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        document_id: Optional[str] = None,
        candidate_chunk_ids: Optional[set[str]] = None,
        min_similarity: float = -1.0,
    ) -> list[tuple[str, float]]:
        """Search index for closest chunks using dot-product cosine similarity.

        Args:
            query_vector: Normalized query embedding vector (dimension D).
            top_k: Maximum candidate passages to return.
            document_id: Optional document identifier filter.
            candidate_chunk_ids: Optional set of permitted chunk identifiers.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            List of (chunk_id, similarity_score) sorted descending by score.
        """
        if query_vector.shape != (self._expected_dim,):
            raise VectorIndexError(
                f"Query vector dimension mismatch: expected ({self._expected_dim},), got {query_vector.shape}"
            )

        if np.isnan(query_vector).any() or np.isinf(query_vector).any():
            raise VectorIndexError("Query vector contains NaN or Infinite values.")

        if len(self._chunk_ids) == 0:
            return []

        # Normalize query vector
        q_norm = np.linalg.norm(query_vector)
        if q_norm < 1e-8:
            raise VectorIndexError("Query vector has zero or near-zero norm.")
        q_unit = query_vector / q_norm

        # Matrix-vector dot product: since index vectors are unit-length, this equals cosine similarity
        scores = np.dot(self._vectors, q_unit)

        # Apply filters
        candidate_indices = []
        for i, (cid, did) in enumerate(zip(self._chunk_ids, self._document_ids)):
            if document_id is not None and did != document_id:
                continue
            if candidate_chunk_ids is not None and cid not in candidate_chunk_ids:
                continue
            if scores[i] < min_similarity:
                continue
            candidate_indices.append(i)

        if not candidate_indices:
            return []

        # Extract candidates and sort descending by score with deterministic tie-breaking by chunk_id
        candidate_scores = [(self._chunk_ids[i], float(scores[i])) for i in candidate_indices]
        candidate_scores.sort(key=lambda x: (-x[1], x[0]))

        return candidate_scores[:top_k]

    def rebuild_from_db(
        self,
        session: Session,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> int:
        """Rebuild the persistent index entirely from database records.

        Args:
            session: Active SQLAlchemy database session.
            embedding_service: Optional embedding service if re-generating vectors.

        Returns:
            Total number of chunks indexed.
        """
        stmt = select(DocumentChunkModel).order_by(DocumentChunkModel.id.asc())
        chunks = list(session.execute(stmt).scalars().all())

        if not chunks:
            self._reset_empty(self._configured_model)
            self._is_degraded = False
            self._degraded_reason = None
            self.save()
            return 0

        target_model = self._configured_model
        if embedding_service:
            target_model = embedding_service.model_name
        else:
            from public_health_sentinel.documents.embeddings import get_embedding_service
            embedding_service = get_embedding_service()
            target_model = embedding_service.model_name

        self._reset_empty(target_model)

        valid_entries: list[tuple[str, str, np.ndarray]] = []
        chunks_needing_embed: list[DocumentChunkModel] = []

        for c in chunks:
            if c.embedding_json and c.embedding_model == target_model:
                try:
                    vec_list = json.loads(c.embedding_json)
                    vec = np.asarray(vec_list, dtype=np.float32)
                    if vec.shape == (self._expected_dim,):
                        valid_entries.append((c.chunk_id, c.document_id, vec))
                        continue
                except Exception:
                    pass
            chunks_needing_embed.append(c)

        if chunks_needing_embed:
            if embedding_service is None:
                raise VectorIndexError(
                    f"{len(chunks_needing_embed)} chunks require embeddings, but no embedding_service was provided."
                )
            texts = [c.text for c in chunks_needing_embed]
            vec_matrix = embedding_service.embed_batch(texts)
            for c, vec in zip(chunks_needing_embed, vec_matrix):
                c.embedding_json = json.dumps(vec.tolist())
                c.embedding_model = target_model
                valid_entries.append((c.chunk_id, c.document_id, vec))
            session.commit()

        if valid_entries:
            self.add_chunks(valid_entries, model_name=target_model)

        self._is_degraded = False
        self._degraded_reason = None
        return len(valid_entries)

    def status(self) -> dict:
        """Retrieve vector index operational status and health metrics."""
        return {
            "index_path": str(self._npz_path),
            "meta_path": str(self._meta_path),
            "index_file_exists": self._npz_path.exists(),
            "meta_file_exists": self._meta_path.exists(),
            "total_vectors": len(self._chunk_ids),
            "dimension": self._expected_dim,
            "active_model_name": self._active_model_name,
            "configured_model_name": self._configured_model,
            "is_degraded": self._is_degraded,
            "degraded_reason": self._degraded_reason,
            "last_updated": self._last_updated.isoformat() if self._last_updated else None,
        }


_global_index: Optional[VectorIndexManager] = None


def get_configured_embedding_model_name() -> str:
    """Resolve expected embedding model name from runtime configuration."""
    config = get_config()
    if config.demo_mode or config.embedding_provider in {"tfidf", "hashing", "lightweight"}:
        return "lightweight-hashing-384"
    elif config.embedding_provider == "mock":
        return "mock-minilm-l6-v2"
    return config.embedding_model_name


def get_vector_index(
    force_new: bool = False,
    embedding_service: Optional[EmbeddingService] = None,
    index_dir: Optional[Union[str, Path]] = None,
) -> VectorIndexManager:
    """Retrieve or initialize singleton VectorIndexManager instance."""
    global _global_index
    expected_model = get_configured_embedding_model_name()

    is_stale = (
        _global_index is not None
        and _global_index.configured_model_name not in {expected_model, "mock-minilm-v1"}
    )

    if _global_index is None or force_new or is_stale:
        emb_svc = embedding_service
        if emb_svc is None:
            from public_health_sentinel.documents.embeddings import get_embedding_service
            emb_svc = get_embedding_service()
        _global_index = VectorIndexManager(
            index_dir=index_dir,
            expected_dim=emb_svc.dimension,
            model_name=expected_model,
        )
    return _global_index



def reset_vector_index() -> None:
    """Reset the global vector index instance (useful in test teardown)."""
    global _global_index
    _global_index = None




def ensure_evidence_index_initialized(
    session: Optional[Session] = None,
    force_rebuild: bool = False,
    embedding_service: Optional[EmbeddingService] = None,
) -> dict[str, Any]:
    """Ensure persistent vector index exists, is populated from DB chunks, and matches active embedding model.

    Idempotent and safe on repeated calls. Does not mutate or duplicate documents or chunks.
    Rebuilds from relational passage records if the index files are missing, empty, or degraded.
    """
    from public_health_sentinel.documents.embeddings import get_embedding_service

    emb_svc = embedding_service or get_embedding_service()
    index = get_vector_index(embedding_service=emb_svc)

    should_close = False
    if session is None:
        try:
            from public_health_sentinel.api.app import app
            from public_health_sentinel.db.session import get_db_session
            override = app.dependency_overrides.get(get_db_session)
            if override:
                session_gen = override()
                if hasattr(session_gen, "__next__"):
                    session = next(session_gen)
                else:
                    session = session_gen
        except Exception:
            pass

    if session is None:
        from public_health_sentinel.db.session import get_engine
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        should_close = True


    try:
        db_chunk_ids = set(session.scalars(select(DocumentChunkModel.chunk_id)).all())
        chunk_count = len(db_chunk_ids)
        if chunk_count == 0:
            return {
                "status": "EMPTY",
                "action": "none",
                "total_vectors": 0,
                "active_model": index.active_model_name,
                "message": "No passage chunks exist in database to index.",
            }

        st = index.status()
        needs_rebuild = (
            force_rebuild
            or not st["index_file_exists"]
            or not st["meta_file_exists"]
            or st["is_degraded"]
            or set(index.chunk_ids) != db_chunk_ids
            or (embedding_service is not None and index.active_model_name != embedding_service.model_name)
        )

        if not needs_rebuild:
            return {
                "status": "HEALTHY",
                "action": "none",
                "total_vectors": index.total_vectors,
                "active_model": index.active_model_name,
                "message": "Vector index is healthy and synchronized with database chunks.",
            }

        logger.info(
            "Vector index initialization required (db_chunks=%d, index_vectors=%d, index_model=%s, active_model=%s). Rebuilding...",
            chunk_count,
            index.total_vectors,
            index.active_model_name,
            emb_svc.model_name,
        )
        rebuilt = index.rebuild_from_db(session=session, embedding_service=emb_svc)
        logger.info("Vector index successfully initialized from database: %d passages indexed.", rebuilt)
        return {
            "status": "HEALTHY" if rebuilt > 0 else "EMPTY",
            "action": "rebuilt",
            "total_vectors": rebuilt,
            "active_model": index.active_model_name,
            "message": f"Vector index successfully initialized from database with {rebuilt} passages.",
        }
    finally:
        if should_close:
            session.close()
