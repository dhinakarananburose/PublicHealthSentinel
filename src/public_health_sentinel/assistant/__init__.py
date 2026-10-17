"""Phase 6C: Evidence-Grounded Public Health Assistant package."""

from public_health_sentinel.assistant.provider import (
    AssistantProviderError,
    BaseGenerationProvider,
    GenerationFailedError,
    GenerationResult,
    MockAnswerGenerationProvider,
    ModelNotFoundError,
    OllamaProvider,
    ProviderHealth,
    ProviderTimeoutError,
    ProviderUnavailableError,
    get_generation_provider,
    set_generation_provider,
)
from public_health_sentinel.assistant.schemas import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantStatusResponse,
    CitationItem,
    RetrievedPassageReference,
)
from public_health_sentinel.assistant.service import (
    EvidenceGroundedAssistant,
    get_assistant,
)

__all__ = [
    "AssistantAskRequest",
    "AssistantAskResponse",
    "AssistantProviderError",
    "AssistantStatusResponse",
    "BaseGenerationProvider",
    "CitationItem",
    "EvidenceGroundedAssistant",
    "GenerationFailedError",
    "GenerationResult",
    "MockAnswerGenerationProvider",
    "ModelNotFoundError",
    "OllamaProvider",
    "ProviderHealth",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "RetrievedPassageReference",
    "get_assistant",
    "get_generation_provider",
    "set_generation_provider",
]
