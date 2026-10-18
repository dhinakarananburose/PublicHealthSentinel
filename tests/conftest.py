"""Global pytest fixtures and state reset hooks."""

import pytest

from public_health_sentinel.config import get_config
from public_health_sentinel.documents.embeddings import reset_embedding_service
from public_health_sentinel.documents.index import reset_vector_index
from public_health_sentinel.assistant.service import reset_assistant
from public_health_sentinel.assistant.provider import reset_generation_provider, set_generation_provider


@pytest.fixture(autouse=True)
def reset_global_caches_and_singletons():
    """Ensure clean global state before and after every test."""
    get_config.cache_clear()
    reset_embedding_service()
    reset_vector_index()
    reset_assistant()
    reset_generation_provider()
    set_generation_provider(None)
    yield
    get_config.cache_clear()
    reset_embedding_service()
    reset_vector_index()
    reset_assistant()
    reset_generation_provider()
    set_generation_provider(None)

