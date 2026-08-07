"""
SENTINEL — Mock AI Provider
==============================
Deterministic, dependency-free responses. Used automatically whenever no
real provider is configured (missing API key, or AI_PROVIDER=mock), and
directly in tests — real providers involve network calls and are
inherently non-deterministic, which makes them a poor fit for assertions.
"""

from app.services.ai_providers.base import AIProvider

_GENERAL_REPLIES = {
    "what_is_sentinel": (
        "**[Sentinel Offline AI]** Sentinel is a real-time fraud investigation platform. "
        "It monitors transactions, constructs case graphs of mule chains, and applies "
        "rule-based and ML scoring to detect and help investigators respond to fraud."
    ),
    "how_freeze": (
        "**[Sentinel Offline AI]** To freeze a suspect account, select a case and use the "
        "**Freeze** action (admin role required). This simulates an API call to the "
        "destination bank to hold the funds."
    ),
    "hello": (
        "**[Sentinel Offline AI]** Hello! I'm Sentinel's AI Copilot, currently running "
        "without a live LLM provider configured. Select a case for context-aware analysis, "
        "or ask me a general question about the platform."
    ),
    "default": (
        "**[Sentinel Offline AI]** No live LLM provider is configured (set `AI_PROVIDER` and "
        "the matching API key). Select a case from the dashboard for a context-aware summary, "
        "or ask a general question about Sentinel."
    ),
}


class MockProvider(AIProvider):
    name = "mock"

    async def generate(self, *, system_prompt: str, user_message: str, context: str) -> str:
        msg = user_message.lower()

        if "what" in msg and "sentinel" in msg:
            return _GENERAL_REPLIES["what_is_sentinel"]
        if "how" in msg and "freeze" in msg:
            return _GENERAL_REPLIES["how_freeze"]
        if "hello" in msg or "hi" in msg:
            return _GENERAL_REPLIES["hello"]

        if context and context.strip():
            return (
                "**[Sentinel Offline AI]** Running without a live LLM provider — here's the "
                f"raw case context available:\n\n{context}\n\n"
                "Review the risk factors above; consider freezing the destination account if risk is high."
            )

        return _GENERAL_REPLIES["default"]
