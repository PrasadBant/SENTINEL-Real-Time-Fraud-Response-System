"""
SENTINEL — Anthropic (Claude) Provider
=========================================
Uses the official `anthropic` Python SDK (AsyncAnthropic), not raw HTTP.

Thinking is explicitly disabled: Claude Opus 5 runs adaptive thinking by
default when the `thinking` param is omitted, and `max_tokens` caps
thinking + response text *together* — for a snappy chat-copilot reply
(not a multi-step reasoning task), leaving thinking on risked eating the
whole token budget before any visible text was written. Disabling
thinking is only valid at effort <= "high" (the default), which is fine
here — we also run at "low" effort for latency.
"""

import os

from app.services.ai_providers.base import AIProvider

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 1024


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic

        # AsyncAnthropic() reads ANTHROPIC_API_KEY from the environment on
        # its own; the factory checks for the key's presence before ever
        # constructing this class (see factory.py), so by the time we get
        # here a key is expected to exist.
        self._client = anthropic.AsyncAnthropic()
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)

    def _build_messages(self, context: str, user_message: str) -> list[dict]:
        return [
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nInvestigator's question: {user_message}",
            }
        ]

    async def generate(self, *, system_prompt: str, user_message: str, context: str) -> str:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            messages=self._build_messages(context, user_message),
        )
        if response.stop_reason == "refusal":
            return "I'm not able to help with that request."
        parts = [block.text for block in response.content if block.type == "text"]
        return "".join(parts).strip()

    async def stream(self, *, system_prompt: str, user_message: str, context: str):
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            messages=self._build_messages(context, user_message),
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk
