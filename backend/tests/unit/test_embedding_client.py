"""Unit tests for embedding_client.

All OpenAI API calls are mocked — no network access.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# embed_text
# ---------------------------------------------------------------------------


def _mock_embedding_response(vector: list[float]) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(embedding=vector)]
    return response


def test_embed_text_returns_vector():
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([0.1, 0.2, 0.3])

    with patch("app.clients.embedding_client.get_embedding_client", return_value=mock_client):
        from app.clients.embedding_client import embed_text

        result = embed_text("TypeScript microservices")

    assert result == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_called_once()


def test_embed_text_passes_correct_model_and_input(monkeypatch):
    monkeypatch.setattr("app.clients.embedding_client.settings.embedding_model", "test-model")
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([0.5])

    with patch("app.clients.embedding_client.get_embedding_client", return_value=mock_client):
        from app.clients.embedding_client import embed_text

        embed_text("some content")

    call_kwargs = mock_client.embeddings.create.call_args
    assert call_kwargs.kwargs["model"] == "test-model"
    assert call_kwargs.kwargs["input"] == "some content"


def test_embed_text_raises_on_empty_string():
    from app.clients.embedding_client import embed_text

    with pytest.raises(ValueError, match="empty"):
        embed_text("")


def test_embed_text_raises_on_whitespace_only():
    from app.clients.embedding_client import embed_text

    with pytest.raises(ValueError, match="empty"):
        embed_text("   ")


def test_embed_text_strips_leading_trailing_whitespace():
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([0.1])

    with patch("app.clients.embedding_client.get_embedding_client", return_value=mock_client):
        from app.clients.embedding_client import embed_text

        embed_text("  some content  ")

    call_kwargs = mock_client.embeddings.create.call_args
    assert call_kwargs.kwargs["input"] == "some content"


# ---------------------------------------------------------------------------
# get_embedding_client — base_url resolution
# ---------------------------------------------------------------------------


def test_get_embedding_client_uses_embedding_base_url(monkeypatch):
    monkeypatch.setattr(
        "app.clients.embedding_client.settings.embedding_base_url", "http://embed-endpoint/v1"
    )
    monkeypatch.setattr(
        "app.clients.embedding_client.settings.llm_base_url", "http://llm-endpoint/v1"
    )
    monkeypatch.setattr("app.clients.embedding_client.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.clients.embedding_client.settings.environment", "local")

    with patch("app.clients.embedding_client.OpenAI") as mock_openai:
        from app.clients.embedding_client import get_embedding_client

        get_embedding_client()

    call_kwargs = mock_openai.call_args.kwargs
    assert call_kwargs["base_url"] == "http://embed-endpoint/v1"


def test_get_embedding_client_falls_back_to_llm_base_url_when_no_separate_key(monkeypatch):
    """No embedding_api_key and no embedding_base_url → inherit LLM endpoint (Azure AI Foundry)."""
    monkeypatch.setattr("app.clients.embedding_client.settings.embedding_base_url", None)
    monkeypatch.setattr("app.clients.embedding_client.settings.embedding_api_key", None)
    monkeypatch.setattr(
        "app.clients.embedding_client.settings.llm_base_url", "http://llm-endpoint/v1"
    )
    monkeypatch.setattr("app.clients.embedding_client.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.clients.embedding_client.settings.environment", "local")

    with patch("app.clients.embedding_client.OpenAI") as mock_openai:
        from app.clients.embedding_client import get_embedding_client

        get_embedding_client()

    call_kwargs = mock_openai.call_args.kwargs
    assert call_kwargs["base_url"] == "http://llm-endpoint/v1"


def test_get_embedding_client_separate_key_uses_openai_default(monkeypatch):
    """EMBEDDING_API_KEY set without EMBEDDING_BASE_URL → OpenAI default, not LM Studio."""
    monkeypatch.setattr("app.clients.embedding_client.settings.embedding_base_url", None)
    monkeypatch.setattr(
        "app.clients.embedding_client.settings.embedding_api_key", "sk-personal-key"
    )
    monkeypatch.setattr(
        "app.clients.embedding_client.settings.llm_base_url", "http://localhost:1234/v1"
    )
    monkeypatch.setattr("app.clients.embedding_client.settings.environment", "local")

    with patch("app.clients.embedding_client.OpenAI") as mock_openai:
        from app.clients.embedding_client import get_embedding_client

        get_embedding_client()

    call_kwargs = mock_openai.call_args.kwargs
    assert call_kwargs["base_url"] is None  # OpenAI default, not LM Studio
