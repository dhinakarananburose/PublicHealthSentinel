"""Answer generation provider abstraction for PublicHealthSentinel Assistant.

Supports local Ollama LLM integration and deterministic mock generation for tests.
Ensures zero paid API dependencies, lightweight initialization, explicit timeouts,
and structured error reporting.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from public_health_sentinel.config import get_config

logger = logging.getLogger("public_health_sentinel.assistant.provider")


class AssistantProviderError(Exception):
    """Base exception for all answer generation provider failures."""
    pass


class ProviderUnavailableError(AssistantProviderError):
    """Raised when the generation provider service is unreachable."""
    pass


class ProviderTimeoutError(AssistantProviderError):
    """Raised when answer generation exceeds the configured deadline."""
    pass


class ModelNotFoundError(AssistantProviderError):
    """Raised when the configured model is not available on the provider."""
    pass


class GenerationFailedError(AssistantProviderError):
    """Raised when the provider returns an error status or malformed response."""
    pass


@dataclass(frozen=True)
class GenerationResult:
    """Standardized output returned by generation providers."""

    text: str
    model: str
    provider: str
    latency_seconds: float
    finish_reason: Optional[str] = "stop"
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    """Diagnostic health assessment for a generation provider."""

    status: str  # "AVAILABLE", "UNAVAILABLE", "ERROR"
    provider_name: str
    model: str
    is_healthy: bool
    message: str
    available_models: list[str] = field(default_factory=list)


class BaseGenerationProvider(ABC):
    """Abstract interface defining answer generation capabilities."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate an answer given user and system prompts."""
        pass

    @abstractmethod
    def check_health(self) -> ProviderHealth:
        """Assess provider connectivity and model readiness."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Configured model name."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string."""
        pass


class OllamaProvider(BaseGenerationProvider):
    """Local Ollama generation provider communicating over HTTP.

    Never loads large model weights into the Python application process.
    Connects to the local Ollama daemon using explicit socket timeouts.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        num_predict: Optional[int] = None,
        keep_alive: Optional[str] = None,
    ) -> None:
        config = get_config()
        self._host = (host or config.ollama_host).rstrip("/")
        self._model = model or config.ollama_model
        self._timeout = timeout_seconds if timeout_seconds is not None else config.ollama_timeout_seconds
        self._num_predict = num_predict if num_predict is not None else config.ollama_num_predict
        self._keep_alive = keep_alive if keep_alive is not None else config.ollama_keep_alive

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def host(self) -> str:
        return self._host

    @property
    def num_predict(self) -> Optional[int]:
        """Configured output token generation limit."""
        return self._num_predict

    @property
    def keep_alive(self) -> str:
        """Configured Ollama model cache duration string."""
        return self._keep_alive

    def check_health(self) -> ProviderHealth:
        """Check whether the local Ollama daemon is running and has the target model."""
        endpoint = f"{self._host}/api/tags"
        req = urllib.request.Request(endpoint, headers={"Accept": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=min(self._timeout, 5.0)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check model availability (e.g. 'llama3.2' matches 'llama3.2:latest')
                model_base = self._model.split(":")[0]
                has_model = any(
                    m == self._model or m.startswith(f"{model_base}:") or m.startswith(model_base)
                    for m in models
                )
                if not has_model:
                    return ProviderHealth(
                        status="UNAVAILABLE",
                        provider_name="ollama",
                        model=self._model,
                        is_healthy=False,
                        message=(
                            f"Ollama server is active at {self._host}, but configured model '{self._model}' "
                            f"is not installed. Available models: {models or 'None'}. "
                            f"Run 'ollama pull {self._model}' to install."
                        ),
                        available_models=models,
                    )

                return ProviderHealth(
                    status="AVAILABLE",
                    provider_name="ollama",
                    model=self._model,
                    is_healthy=True,
                    message=f"Ollama server active at {self._host} with model '{self._model}'.",
                    available_models=models,
                )

        except urllib.error.URLError as exc:
            return ProviderHealth(
                status="UNAVAILABLE",
                provider_name="ollama",
                model=self._model,
                is_healthy=False,
                message=(
                    f"Ollama server is not reachable at {self._host} ({exc.reason}). "
                    f"Ensure the Ollama application is running locally."
                ),
                available_models=[],
            )
        except Exception as exc:
            return ProviderHealth(
                status="ERROR",
                provider_name="ollama",
                model=self._model,
                is_healthy=False,
                message=f"Error probing Ollama service at {self._host}: {exc}",
                available_models=[],
            )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Execute text generation through Ollama /api/generate."""
        start_time = time.perf_counter()
        endpoint = f"{self._host}/api/generate"

        num_predict = kwargs.get("num_predict", self._num_predict)
        keep_alive = kwargs.get("keep_alive", self._keep_alive)

        options: dict[str, Any] = {
            "temperature": kwargs.get("temperature", 0.1),
            "top_p": kwargs.get("top_p", 0.9),
        }
        if num_predict is not None and num_predict > 0:
            options["num_predict"] = int(num_predict)

        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": options,
        }
        if keep_alive is not None and str(keep_alive).strip():
            payload["keep_alive"] = str(keep_alive).strip()

        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=json_bytes,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                elapsed = time.perf_counter() - start_time
                resp_data = json.loads(resp.read().decode("utf-8"))
                output_text = resp_data.get("response", "").strip()
                finish_reason = "stop" if resp_data.get("done") else "incomplete"

                return GenerationResult(
                    text=output_text,
                    model=self._model,
                    provider="ollama",
                    latency_seconds=elapsed,
                    finish_reason=finish_reason,
                    raw_metadata={
                        "total_duration": resp_data.get("total_duration"),
                        "load_duration": resp_data.get("load_duration"),
                        "prompt_eval_duration": resp_data.get("prompt_eval_duration"),
                        "eval_duration": resp_data.get("eval_duration"),
                        "eval_count": resp_data.get("eval_count"),
                        "prompt_eval_count": resp_data.get("prompt_eval_count"),
                    },
                )

        except urllib.error.HTTPError as exc:
            elapsed = time.perf_counter() - start_time
            if exc.code == 404:
                raise ModelNotFoundError(
                    f"Ollama model '{self._model}' was not found on server {self._host}. "
                    f"Please run 'ollama pull {self._model}'."
                ) from exc
            error_body = exc.read().decode("utf-8", errors="replace")
            raise GenerationFailedError(
                f"Ollama server returned HTTP {exc.code}: {error_body}"
            ) from exc

        except urllib.error.URLError as exc:
            elapsed = time.perf_counter() - start_time
            if "timed out" in str(exc.reason).lower():
                raise ProviderTimeoutError(
                    f"Ollama generation timed out after {self._timeout:.1f}s at {self._host}."
                ) from exc
            raise ProviderUnavailableError(
                f"Cannot connect to local Ollama server at {self._host}: {exc.reason}. "
                f"Verify that Ollama is started."
            ) from exc

        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"Ollama generation timed out after {self._timeout:.1f}s at {self._host}."
            ) from exc

        except Exception as exc:
            raise GenerationFailedError(f"Unexpected generation failure: {exc}") from exc


class MockAnswerGenerationProvider(BaseGenerationProvider):
    """Deterministic generation provider for automated offline testing.

    Can be programmed with custom responses, refusal triggers, or simulated failures.
    """

    def __init__(
        self,
        model_name: str = "mock-health-assistant-v1",
        default_response: Optional[str] = None,
        should_fail: bool = False,
        failure_error: Optional[Exception] = None,
    ) -> None:
        self._model = model_name
        self._default_response = default_response
        self._should_fail = should_fail
        self._failure_error = failure_error
        self.call_history: list[dict[str, Any]] = []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "mock"

    def set_response(self, text: str) -> None:
        """Program the response returned by generate()."""
        self._default_response = text

    def set_failure(self, error: Exception) -> None:
        """Program a failure exception to be raised on generate()."""
        self._should_fail = True
        self._failure_error = error

    def clear_failure(self) -> None:
        """Clear failure mode."""
        self._should_fail = False
        self._failure_error = None

    def check_health(self) -> ProviderHealth:
        if self._should_fail:
            return ProviderHealth(
                status="UNAVAILABLE",
                provider_name="mock",
                model=self._model,
                is_healthy=False,
                message="Mock generation provider in simulated failure mode.",
            )
        return ProviderHealth(
            status="AVAILABLE",
            provider_name="mock",
            model=self._model,
            is_healthy=True,
            message="Mock generation provider ready for testing.",
            available_models=[self._model],
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        start_time = time.perf_counter()
        self.call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "kwargs": kwargs,
        })

        if self._should_fail:
            if self._failure_error:
                raise self._failure_error
            raise ProviderUnavailableError("Simulated mock provider connection failure.")

        # If a canned response is configured, return it
        if self._default_response is not None:
            text = self._default_response
        elif kwargs.get("num_predict") is not None and kwargs["num_predict"] <= 25:
            # Concise mode grounded mock answer
            text = "Statistical surge alerts trigger when observed counts exceed baseline plus 2.5 MAD [E1]."
        else:
            # Generate a grounded mock answer referencing evidence tags [E1], [E2]
            text = (
                "Based on the surveillance guidance, emergency departments monitor daily encounters "
                "for respiratory syndrome [E1]. Statistical surge alerts trigger when observed counts "
                "exceed baseline plus 2.5 times the median absolute deviation [E1]. "
                "Secondary epidemiological reviews are conducted within 4 hours to eliminate batching artifacts [E1]."
            )

        elapsed = time.perf_counter() - start_time
        return GenerationResult(
            text=text,
            model=self._model,
            provider="mock",
            latency_seconds=elapsed,
            finish_reason="stop",
            raw_metadata={"mock": True},
        )


class DemoGenerationProvider(BaseGenerationProvider):
    """Zero-overhead generation provider for public portfolio demo mode.

    Returns evidence-first responses directly without requiring Ollama or GPU/CPU
    neural network inference, adhering strictly to the 512 MB free cloud tier limit.
    """

    def __init__(self, model_name: str = "evidence-first-demo") -> None:
        self._model = model_name

    @property
    def provider_name(self) -> str:
        return "demo"

    @property
    def model_name(self) -> str:
        return self._model

    def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            status="AVAILABLE",
            provider_name="demo",
            model=self._model,
            is_healthy=True,
            message="Public demonstration mode: evidence-first responses active (zero local neural model overhead).",
            available_models=[self._model],
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        return GenerationResult(
            text="PUBLIC DEMO NOTICE: In this free-tier cloud demonstration (512 MB RAM limit), local LLM neural synthesis is disabled to respect hosting budget constraints (₹0/month). Below are the authentic, retrieved reference protocol passages with complete citation provenance matching your inquiry.",
            model=self._model,
            provider="demo",
            latency_seconds=0.001,
            finish_reason="demo_mode",
            raw_metadata={"demo_mode": True},
        )


_active_provider: Optional[BaseGenerationProvider] = None


def get_generation_provider() -> BaseGenerationProvider:
    """Retrieve active generation provider based on runtime application configuration."""
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    config = get_config()
    if config.generation_provider == "mock":
        _active_provider = MockAnswerGenerationProvider()
    elif config.generation_provider == "demo" or config.demo_mode:
        _active_provider = DemoGenerationProvider()
    else:
        _active_provider = OllamaProvider(
            host=config.ollama_host,
            model=config.ollama_model,
            timeout_seconds=config.ollama_timeout_seconds,
        )
    return _active_provider


def set_generation_provider(provider: Optional[BaseGenerationProvider]) -> None:
    """Override generation provider (useful in automated test fixtures)."""
    global _active_provider
    _active_provider = provider
