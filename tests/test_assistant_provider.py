"""Unit tests for Phase 6C Assistant generation providers."""

import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from public_health_sentinel.assistant.provider import (
    GenerationFailedError,
    MockAnswerGenerationProvider,
    ModelNotFoundError,
    OllamaProvider,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def test_mock_provider_basic_generation():
    """Verify MockAnswerGenerationProvider returns formatted GenerationResult."""
    provider = MockAnswerGenerationProvider(model_name="test-mock-llm")
    assert provider.model_name == "test-mock-llm"
    assert provider.provider_name == "mock"

    res = provider.generate(prompt="What is syndromic surveillance?")
    assert "[E1]" in res.text
    assert res.model == "test-mock-llm"
    assert res.provider == "mock"
    assert res.latency_seconds >= 0.0
    assert len(provider.call_history) == 1


def test_mock_provider_custom_canned_response():
    """Verify programmed canned responses."""
    provider = MockAnswerGenerationProvider()
    provider.set_response("Custom public health answer [E1].")

    res = provider.generate(prompt="Test prompt")
    assert res.text == "Custom public health answer [E1]."


def test_mock_provider_failure_mode():
    """Verify programmed failure mode raises expected exception."""
    provider = MockAnswerGenerationProvider()
    provider.set_failure(ProviderUnavailableError("Simulated server down"))

    health = provider.check_health()
    assert health.is_healthy is False
    assert health.status == "UNAVAILABLE"

    with pytest.raises(ProviderUnavailableError, match="Simulated server down"):
        provider.generate(prompt="Test prompt")

    provider.clear_failure()
    assert provider.check_health().is_healthy is True


def test_ollama_provider_health_check_available():
    """Verify OllamaProvider check_health correctly detects installed model."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=5.0)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "models": [{"name": "llama3.2:latest"}, {"name": "phi3:mini"}]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        health = provider.check_health()
        assert health.is_healthy is True
        assert health.status == "AVAILABLE"
        assert "llama3.2:latest" in health.available_models


def test_ollama_provider_health_check_model_missing():
    """Verify OllamaProvider check_health reports UNAVAILABLE when target model is absent."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=5.0)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "models": [{"name": "mistral:latest"}]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        health = provider.check_health()
        assert health.is_healthy is False
        assert health.status == "UNAVAILABLE"
        assert "not installed" in health.message


def test_ollama_provider_health_check_connection_refused():
    """Verify OllamaProvider check_health reports UNAVAILABLE when daemon is not running."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=5.0)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        health = provider.check_health()
        assert health.is_healthy is False
        assert health.status == "UNAVAILABLE"
        assert "not reachable" in health.message


def test_ollama_provider_generate_success():
    """Verify OllamaProvider parses successful /api/generate response."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=10.0)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "response": "Respiratory baseline is calculated over a 28-day window [E1].",
        "done": True,
        "total_duration": 1500000000,
        "eval_count": 42,
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = provider.generate(prompt="What is the baseline window?")
        assert res.text == "Respiratory baseline is calculated over a 28-day window [E1]."
        assert res.model == "llama3.2:latest"
        assert res.provider == "ollama"
        assert res.raw_metadata["eval_count"] == 42


def test_ollama_provider_generate_404_model_not_found():
    """Verify OllamaProvider raises ModelNotFoundError on HTTP 404."""
    provider = OllamaProvider(host="http://localhost:11434", model="nonexistent:model", timeout_seconds=5.0)

    http_err = urllib.error.HTTPError(
        url="http://localhost:11434/api/generate",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=MagicMock(),
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(ModelNotFoundError, match="was not found"):
            provider.generate(prompt="Test prompt")


def test_ollama_provider_generate_timeout():
    """Verify OllamaProvider raises ProviderTimeoutError on timeout."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=2.0)

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Socket timed out")):
        with pytest.raises(ProviderTimeoutError, match="timed out"):
            provider.generate(prompt="Test prompt")


def test_ollama_provider_custom_timeout_configuration():
    """Verify OllamaProvider accepts custom timeout override and defaults to config (90s)."""
    provider_default = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest")
    assert provider_default._timeout == 90.0

    provider_custom = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=45.0)
    assert provider_custom._timeout == 45.0


def test_ollama_provider_timeout_error_formatting():
    """Verify ProviderTimeoutError includes formatted timeout and host."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=90.0)

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            provider.generate(prompt="Test prompt")
        assert "90.0s" in str(exc_info.value)
        assert "http://localhost:11434" in str(exc_info.value)


def test_ollama_provider_urlerror_timeout_detection():
    """Verify ProviderTimeoutError is raised when URLError mentions timed out."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest", timeout_seconds=90.0)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("The read operation timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            provider.generate(prompt="Test prompt")
        assert "90.0s" in str(exc_info.value)


def test_ollama_provider_num_predict_and_keep_alive_defaults():
    """Verify OllamaProvider sets num_predict and keep_alive defaults from config."""
    provider = OllamaProvider(host="http://localhost:11434", model="llama3.2:latest")
    assert provider.num_predict == 40
    assert provider.keep_alive == "60m"

    custom_provider = OllamaProvider(
        host="http://localhost:11434",
        model="llama3.2:latest",
        num_predict=25,
        keep_alive="10m",
    )
    assert custom_provider.num_predict == 25
    assert custom_provider.keep_alive == "10m"


def test_ollama_provider_payload_serialization():
    """Verify num_predict and keep_alive are correctly serialized into HTTP request payload."""
    provider = OllamaProvider(
        host="http://localhost:11434",
        model="llama3.2:latest",
        num_predict=30,
        keep_alive="30m",
    )

    captured_payload = None

    def mock_urlopen(req, timeout):
        nonlocal captured_payload
        captured_payload = json.loads(req.data.decode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "response": "Answer text [E1]",
            "done": True,
            "total_duration": 1000000000,
            "load_duration": 100000000,
            "prompt_eval_duration": 200000000,
            "eval_duration": 700000000,
            "eval_count": 28,
            "prompt_eval_count": 120,
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        res = provider.generate(prompt="What is the surge protocol?")
        assert res.text == "Answer text [E1]"
        assert captured_payload is not None
        assert captured_payload["options"]["num_predict"] == 30
        assert captured_payload["options"]["temperature"] == 0.1
        assert captured_payload["keep_alive"] == "30m"
        assert res.raw_metadata["eval_count"] == 28
        assert res.raw_metadata["load_duration"] == 100000000


def test_ollama_provider_kwargs_override():
    """Verify kwargs in generate() override instance num_predict and keep_alive."""
    provider = OllamaProvider(
        host="http://localhost:11434",
        model="llama3.2:latest",
        num_predict=40,
        keep_alive="60m",
    )

    captured_payload = None

    def mock_urlopen(req, timeout):
        nonlocal captured_payload
        captured_payload = json.loads(req.data.decode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "Short [E1]", "done": True}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        provider.generate(prompt="Test", num_predict=15, keep_alive="5m")
        assert captured_payload["options"]["num_predict"] == 15
        assert captured_payload["keep_alive"] == "5m"

