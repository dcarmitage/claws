"""Anthropic API provider."""

from __future__ import annotations

from typing import AsyncIterator

import httpx

from claws.providers.base import Provider, Message, Response


class AnthropicProvider(Provider):
    """Provider for Anthropic's Messages API."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_request(self, messages: list[Message], **kwargs) -> dict:
        system = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        body = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system:
            body["system"] = system
        return body

    async def complete(self, messages: list[Message], **kwargs) -> Response:
        body = self._build_request(messages, **kwargs)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(self.API_URL, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json()

        content = data["content"][0]["text"] if data.get("content") else ""
        usage = data.get("usage", {})
        return Response(
            content=content,
            model=data.get("model", self.model),
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
        )

    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        body = self._build_request(messages, **kwargs)
        body["stream"] = True
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", self.API_URL, headers=self._headers(), json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            if data.get("type") == "content_block_delta":
                                text = data.get("delta", {}).get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
