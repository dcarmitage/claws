"""Tests for provider registry, AnthropicProvider, OpenAICompatProvider."""

import pytest
from unittest.mock import patch, MagicMock

from claws.config import ProviderConfig
from claws.providers.base import Provider, Message, Response
from claws.providers.registry import get_provider
from claws.providers.anthropic import AnthropicProvider
from claws.providers.openai_compat import OpenAICompatProvider


# ---------------------------------------------------------------------------
# Message and Response dataclasses
# ---------------------------------------------------------------------------

class TestMessage:
    def test_creation(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


class TestResponse:
    def test_creation(self):
        r = Response(content="hi", model="m")
        assert r.content == "hi"
        assert r.tokens_in == 0
        assert r.tokens_out == 0

    def test_total_tokens(self):
        r = Response(content="hi", model="m", tokens_in=10, tokens_out=20)
        assert r.total_tokens == 30


# ---------------------------------------------------------------------------
# Registry dispatch
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_anthropic_type(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        cfg = ProviderConfig(name="default", type="anthropic", model="claude-sonnet-4-5-20250929")
        prov = get_provider(cfg)
        assert isinstance(prov, AnthropicProvider)
        assert prov.api_key == "test-key"
        assert prov.model == "claude-sonnet-4-5-20250929"

    def test_openai_type(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        cfg = ProviderConfig(name="oai", type="openai", model="gpt-4o")
        prov = get_provider(cfg)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.model == "gpt-4o"
        assert prov.base_url == "https://api.openai.com/v1"

    def test_ollama_type(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = ProviderConfig(name="local", type="ollama", model="llama3")
        prov = get_provider(cfg)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.base_url == "http://localhost:11434/v1"
        assert prov.model == "llama3"

    def test_openai_compatible_type(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = ProviderConfig(
            name="custom", type="openai-compatible", model="foo",
            base_url="http://my-host:8080/v1",
        )
        prov = get_provider(cfg)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.base_url == "http://my-host:8080/v1"

    def test_anthropic_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = ProviderConfig(name="default", type="anthropic", model="m")
        with pytest.raises(ValueError, match="API key not found"):
            get_provider(cfg)

    def test_openai_compat_with_custom_base_url(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = ProviderConfig(
            name="custom", type="openai-compatible", model="m",
            base_url="http://example.com/v1",
        )
        prov = get_provider(cfg)
        assert prov.base_url == "http://example.com/v1"

    def test_default_base_url_for_plain_openai(self, monkeypatch):
        """Non-ollama, non-custom type without base_url defaults to openai."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = ProviderConfig(name="x", type="something-else", model="m")
        prov = get_provider(cfg)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.base_url == "https://api.openai.com/v1"


# ---------------------------------------------------------------------------
# AnthropicProvider init
# ---------------------------------------------------------------------------

class TestAnthropicProvider:
    def test_init(self):
        p = AnthropicProvider(api_key="key", model="claude-3-opus")
        assert p.api_key == "key"
        assert p.model == "claude-3-opus"

    def test_default_model(self):
        p = AnthropicProvider(api_key="key")
        assert p.model == "claude-opus-4-6"

    def test_headers(self):
        p = AnthropicProvider(api_key="secret")
        h = p._headers()
        assert h["x-api-key"] == "secret"
        assert "anthropic-version" in h

    def test_build_request_separates_system(self):
        p = AnthropicProvider(api_key="k")
        msgs = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
        ]
        body = p._build_request(msgs)
        assert body["system"] == "You are helpful."
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"

    def test_build_request_no_system(self):
        p = AnthropicProvider(api_key="k")
        msgs = [Message(role="user", content="Hello")]
        body = p._build_request(msgs)
        assert "system" not in body
        assert len(body["messages"]) == 1

    def test_is_provider_subclass(self):
        p = AnthropicProvider(api_key="k")
        assert isinstance(p, Provider)


# ---------------------------------------------------------------------------
# OpenAICompatProvider init
# ---------------------------------------------------------------------------

class TestOpenAICompatProvider:
    def test_init(self):
        p = OpenAICompatProvider(model="gpt-4o", api_key="k", base_url="http://x/v1")
        assert p.model == "gpt-4o"
        assert p.api_key == "k"
        assert p.base_url == "http://x/v1"

    def test_default_base_url(self):
        p = OpenAICompatProvider(model="m")
        assert p.base_url == "https://api.openai.com/v1"

    def test_trailing_slash_stripped(self):
        p = OpenAICompatProvider(model="m", base_url="http://x/v1/")
        assert p.base_url == "http://x/v1"

    def test_headers_with_key(self):
        p = OpenAICompatProvider(model="m", api_key="bearer-tok")
        h = p._headers()
        assert h["authorization"] == "Bearer bearer-tok"

    def test_headers_without_key(self):
        p = OpenAICompatProvider(model="m")
        h = p._headers()
        assert "authorization" not in h

    def test_build_request(self):
        p = OpenAICompatProvider(model="gpt-4o")
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="hi"),
        ]
        body = p._build_request(msgs)
        assert body["model"] == "gpt-4o"
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "system"

    def test_is_provider_subclass(self):
        p = OpenAICompatProvider(model="m")
        assert isinstance(p, Provider)
