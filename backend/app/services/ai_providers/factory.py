"""
SENTINEL — AI Provider Factory
==================================
Single place that decides which AIProvider implementation actually
handles a copilot request. app/api/copilot.py calls get_provider() and
never imports a specific vendor SDK.
"""

import logging
import os

from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.base import AIProvider
from app.services.ai_providers.huggingface_provider import HuggingFaceProvider
from app.services.ai_providers.mock_provider import MockProvider
from app.services.ai_providers.stubs import GeminiProvider, OllamaProvider, OpenAIProvider

logger = logging.getLogger("sentinel")

_REGISTRY: dict[str, type[AIProvider]] = {
    "anthropic": AnthropicProvider,
    "huggingface": HuggingFaceProvider,
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}

# Which env var each real provider needs — used to decide auto-detection
# order and whether to fall back to Mock. Providers absent from this dict
# (mock, and the stubs) don't gate on a key.
_REQUIRED_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "huggingface": "HF_API_KEY",
}


def get_provider() -> AIProvider:
    """
    Select an AIProvider based on the AI_PROVIDER env var.

    - Unset: auto-detect — prefer Anthropic if ANTHROPIC_API_KEY is set,
      else Hugging Face if HF_API_KEY is set (preserves the
      pre-abstraction default behavior), else Mock.
    - Set to a real provider whose required key is missing: log a warning
      and fall back to Mock rather than failing every chat request.
    - Set to an unimplemented stub (openai/gemini/ollama): raises
      immediately — the operator explicitly asked for something that
      isn't built yet, so fail loud instead of silently serving Mock.
    - Set to an unrecognized value: raises.
    """
    requested = os.getenv("AI_PROVIDER")

    if not requested:
        if os.getenv("ANTHROPIC_API_KEY"):
            return AnthropicProvider()
        if os.getenv("HF_API_KEY"):
            return HuggingFaceProvider()
        return MockProvider()

    requested = requested.lower()
    if requested not in _REGISTRY:
        raise ValueError(f"Unknown AI_PROVIDER={requested!r}. Valid options: {', '.join(_REGISTRY)}")

    required_key = _REQUIRED_KEY_ENV.get(requested)
    if required_key and not os.getenv(required_key):
        logger.warning(
            "AI_PROVIDER=%s but %s is not set — falling back to mock provider",
            requested,
            required_key,
        )
        return MockProvider()

    return _REGISTRY[requested]()
