"""Local embedding model integration for PublicHealthSentinel Phase 6B.1.

Wraps compact sentence-transformer models for local semantic encoding with:
- Dimension validation (384 dimensions for all-MiniLM-L6-v2)
- NaN / Infinity rejection
- L2 unit-norm normalization for dot-product cosine similarity
- Batch encoding to constrain memory on 8 GB RAM systems
- Lazy on-demand loading to prevent startup latency
- Protocol abstraction for fast offline testing
"""

from __future__ import annotations

import hashlib
from typing import Optional, Protocol

import numpy as np

from public_health_sentinel.config import get_config


class EmbeddingError(Exception):
    """Base exception for embedding extraction failures."""
    pass


class EmbeddingModelError(EmbeddingError):
    """Raised when the embedding model fails to initialize or load weights."""
    pass


class EmbeddingValueError(EmbeddingError):
    """Raised when an embedding output contains NaN, Inf, or invalid dimensions."""
    pass


class EmbeddingService(Protocol):
    """Protocol interface for embedding providers."""

    @property
    def model_name(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...

    def embed_text(self, text: str) -> np.ndarray:
        ...

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        ...


class LocalSentenceTransformerEmbeddingService:
    """Local embedding generator using compact sentence-transformer architectures."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        expected_dim: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        config = get_config()
        self._model_name: str = model_name or config.embedding_model_name
        self._expected_dim: int = expected_dim or config.embedding_dimension
        self._batch_size: int = batch_size or config.embedding_batch_size
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._expected_dim

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        """Explicitly load model weights into memory on first analytical use."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            # Load model onto CPU with safe offline/cached priority
            self._model = SentenceTransformer(self._model_name, device="cpu")
        except Exception as exc:
            raise EmbeddingModelError(
                f"Failed to load local embedding model '{self._model_name}': {exc}"
            ) from exc

    def _ensure_model(self) -> None:
        if self._model is None:
            self.load_model()

    def _validate_vector(self, vec: np.ndarray, index: int = 0) -> np.ndarray:
        """Validate embedding dimension, finiteness, and normalize to unit length."""
        if not isinstance(vec, np.ndarray):
            vec = np.asarray(vec, dtype=np.float32)
        else:
            vec = vec.astype(np.float32)

        if vec.shape != (self._expected_dim,):
            raise EmbeddingValueError(
                f"Vector [{index}] dimension mismatch: expected {self._expected_dim}, got {vec.shape}"
            )

        if np.isnan(vec).any():
            raise EmbeddingValueError(f"Vector [{index}] contains NaN values.")

        if np.isinf(vec).any():
            raise EmbeddingValueError(f"Vector [{index}] contains infinite values.")

        # Ensure unit L2 normalization
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec = vec / norm
        else:
            raise EmbeddingValueError(f"Vector [{index}] has zero or near-zero norm.")

        return vec

    def embed_text(self, text: str) -> np.ndarray:
        """Compute normalized dense embedding for a single text string."""
        if not text or not text.strip():
            raise EmbeddingValueError("Cannot embed empty or whitespace-only text.")

        self._ensure_model()
        try:
            raw = self._model.encode(
                text.strip(),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return self._validate_vector(raw)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Embedding generation failed for text: {exc}") from exc

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Compute normalized dense embeddings for a collection of text passages in batches."""
        if not texts:
            return np.empty((0, self._expected_dim), dtype=np.float32)

        cleaned_texts = [t.strip() for t in texts]
        for i, t in enumerate(cleaned_texts):
            if not t:
                raise EmbeddingValueError(f"Batch item at index {i} is empty or whitespace-only.")

        self._ensure_model()
        try:
            raw_matrix = self._model.encode(
                cleaned_texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if not isinstance(raw_matrix, np.ndarray):
                raw_matrix = np.asarray(raw_matrix, dtype=np.float32)

            validated_vectors = []
            for i, vec in enumerate(raw_matrix):
                validated_vectors.append(self._validate_vector(vec, index=i))

            return np.vstack(validated_vectors).astype(np.float32)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Batch embedding generation failed: {exc}") from exc


class DeterministicMockEmbeddingService:
    """Deterministic, offline embedding mock for fast unit tests without model downloads.

    Generates stable, pseudo-semantic normalized unit vectors from SHA-256 digests.
    """

    def __init__(
        self,
        model_name: str = "mock-minilm-l6-v2",
        expected_dim: int = 384,
    ) -> None:
        self._model_name = model_name
        self._expected_dim = expected_dim

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._expected_dim

    def _generate_vector(self, text: str) -> np.ndarray:
        """Generate deterministic pseudo-random unit vector seeded by text content."""
        if not text or not text.strip():
            raise EmbeddingValueError("Cannot embed empty or whitespace-only text.")

        # Seed pseudo-random generator with text digest
        seed = int(hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self._expected_dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm

    def embed_text(self, text: str) -> np.ndarray:
        return self._generate_vector(text)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._expected_dim), dtype=np.float32)
        vectors = [self._generate_vector(t) for t in texts]
        return np.vstack(vectors).astype(np.float32)


class HashingTfidfEmbeddingService:
    """Lightweight, offline embedding generator using stateless n-gram feature hashing.

    Produces exact unit-norm L2 vectors of the requested dimension (default: 384) without
    importing PyTorch or SentenceTransformers, keeping memory usage <250 MB for free cloud tiers.
    """

    def __init__(
        self,
        model_name: str = "lightweight-hashing-384",
        expected_dim: int = 384,
    ) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self._model_name = model_name
        self._expected_dim = expected_dim
        self._vectorizer = HashingVectorizer(
            n_features=expected_dim,
            norm="l2",
            alternate_sign=False,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b\w+\b",
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._expected_dim

    def embed_text(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            raise EmbeddingValueError("Cannot embed empty or whitespace-only text.")
        vec = self._vectorizer.transform([text.strip()]).toarray()[0].astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._expected_dim), dtype=np.float32)
        matrix = self._vectorizer.transform([t.strip() if t and t.strip() else "" for t in texts]).toarray().astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        return matrix / norms


_active_service: Optional[EmbeddingService] = None


def get_embedding_service(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    force_new: bool = False,
) -> EmbeddingService:
    """Retrieve or initialize singleton embedding service instance."""
    global _active_service
    if _active_service is not None and not force_new and provider is None and model_name is None:
        return _active_service

    config = get_config()
    chosen_provider = (provider or config.embedding_provider).lower()

    if chosen_provider == "mock":
        service: EmbeddingService = DeterministicMockEmbeddingService(
            model_name=model_name or "mock-minilm-l6-v2",
            expected_dim=config.embedding_dimension,
        )
    elif chosen_provider in {"tfidf", "hashing", "lightweight"} or config.demo_mode:
        service = HashingTfidfEmbeddingService(
            model_name=model_name or "lightweight-hashing-384",
            expected_dim=config.embedding_dimension,
        )
    else:
        service = LocalSentenceTransformerEmbeddingService(
            model_name=model_name or config.embedding_model_name,
            expected_dim=config.embedding_dimension,
            batch_size=config.embedding_batch_size,
        )

    if not force_new and provider is None and model_name is None:
        _active_service = service
    return service

