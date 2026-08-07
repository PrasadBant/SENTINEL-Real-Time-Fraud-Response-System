"""
SENTINEL — Stub AI Providers
================================
OpenAI, Gemini, and Ollama are declared here to complete the
AI_PROVIDER selection surface, but are not implemented yet — only
Anthropic and Mock have real adapters (see anthropic_provider.py /
mock_provider.py). Selecting one of these via AI_PROVIDER raises
immediately at startup rather than failing confusingly on first request;
the factory does not silently fall back for a stub the operator
explicitly asked for (unlike a missing API key, which does fall back —
see factory.py).

To implement one: subclass AIProvider (see base.py), implement
`generate()` (and optionally `stream()`), and register it in
factory.py's PROVIDERS dict.
"""

from app.services.ai_providers.base import AIProvider


class _StubProvider(AIProvider):
    def __init__(self, *_, **__):
        raise NotImplementedError(
            f"AI_PROVIDER={self.name!r} is not implemented yet. "
            f"Available providers: anthropic, huggingface, mock. "
            f"See app/services/ai_providers/stubs.py to add one."
        )

    # AIProvider.generate is abstract — ABC checks that every abstract
    # method is overridden *before* __init__ ever runs, so without this
    # Python raises its own generic "Can't instantiate abstract class"
    # TypeError and the helpful NotImplementedError above never fires.
    # This body is unreachable (construction always raises first).
    async def generate(self, *, system_prompt: str, user_message: str, context: str) -> str:
        raise NotImplementedError


class OpenAIProvider(_StubProvider):
    name = "openai"


class GeminiProvider(_StubProvider):
    name = "gemini"


class OllamaProvider(_StubProvider):
    name = "ollama"
