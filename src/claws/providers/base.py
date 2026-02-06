"""Base provider interface for LLM backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class Message:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class Response:
    """An LLM response."""
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


class Provider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def complete(self, messages: list[Message], **kwargs) -> Response:
        """Send messages and get a complete response."""
        ...

    @abstractmethod
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        """Send messages and stream the response text."""
        ...
