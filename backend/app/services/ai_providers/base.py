"""
SENTINEL — AI Provider Interface
===================================
Abstracts the LLM backend behind one async method so the copilot route
never talks to a specific vendor SDK directly. Swap providers via the
AI_PROVIDER env var (see app/services/ai_providers/factory.py) — nothing
in app/api/copilot.py needs to change when the provider changes.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AIProvider(ABC):
    """
    A provider turns (system prompt, conversation history, latest user
    message) into a reply. Implementations should raise on failure rather
    than returning an empty string — the caller (copilot.py) is
    responsible for catching provider errors and falling back to
    MockProvider, not each provider silently degrading itself.
    """

    #: Short identifier used in logs and the /api/copilot/chat response
    #: (e.g. so the frontend/tests can tell which backend actually answered).
    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        """Return the complete reply as a single string (non-streaming)."""
        raise NotImplementedError

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]:
        """
        Yield the reply incrementally, chunk by chunk. Default
        implementation falls back to a single chunk from generate() —
        providers that support real token streaming (Anthropic) override
        this for a genuinely incremental response.
        """
        yield await self.generate(
            system_prompt=system_prompt, user_message=user_message, context=context
        )
