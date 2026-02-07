"""OpenAI-compatible provider.

Works with: OpenAI, Ollama, OpenRouter, Together, Groq, LM Studio,
and any other endpoint that implements the OpenAI chat completions API.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from claws.providers.base import Provider, Message, Response


class OpenAICompatProvider(Provider):
    """Provider for any OpenAI-compatible chat completions API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_request(self, messages: list[Message], **kwargs) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

    async def complete(self, messages: list[Message], **kwargs) -> Response:
        body = self._build_request(messages, **kwargs)
        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, headers=self._headers(), json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code in (401, 403):
                raise RuntimeError(
                    f"Authentication failed (HTTP {status_code}) for {self.base_url}. "
                    "Check your API key configuration.\n"
                    "Run: claws doctor"
                ) from e
            raise RuntimeError(
                f"API error (HTTP {status_code}) from {self.base_url}: {e}"
            ) from e
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to {self.base_url}. "
                "Check your network connection and base_url setting.\n"
                "Run: claws doctor"
            ) from e

        choice = data["choices"][0] if data.get("choices") else {}
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return Response(
            content=content,
            model=data.get("model", self.model),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )

    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        body = self._build_request(messages, **kwargs)
        body["stream"] = True
        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", url, headers=self._headers(), json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            delta = data["choices"][0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
