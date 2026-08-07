"""
SENTINEL — Hugging Face Provider
====================================
The original copilot backend, now just one AIProvider implementation
among several instead of the only option hardcoded into the route.
Uses the HF serverless Inference API's OpenAI-compatible chat-completions
endpoint via httpx (async — see the Phase 1 fix history for why this must
never be a blocking `urllib` call).
"""

import os

import httpx

from app.services.ai_providers.base import AIProvider, format_user_content

_HF_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct/v1/chat/completions"


class HuggingFaceProvider(AIProvider):
    name = "huggingface"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("HF_API_KEY")
        if not self._api_key:
            raise RuntimeError("HuggingFaceProvider requires HF_API_KEY to be set")

    async def generate(self, *, system_prompt: str, user_message: str, context: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": format_user_content(context, user_message)},
            ],
            "max_tokens": 300,
            "temperature": 0.3,
            "top_p": 0.9,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(_HF_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            choices = result.get("choices", [])
            if not choices:
                raise RuntimeError("Hugging Face response had no choices")
            return choices[0]["message"]["content"].strip()
