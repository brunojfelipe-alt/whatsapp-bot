"""Fallback opcional via LLM (OpenRouter) para perguntas fora do script."""
from __future__ import annotations

import os

import httpx

from app.config import BusinessConfig

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def llm_available(config: BusinessConfig) -> bool:
    return config.llm_enabled and bool(os.getenv("OPENROUTER_API_KEY"))


async def ask_llm(config: BusinessConfig, question: str) -> str | None:
    """Retorna resposta do LLM ou None se indisponível/erro (chamador deve usar fallback padrão)."""
    if not llm_available(config):
        return None

    api_key = os.getenv("OPENROUTER_API_KEY")
    context = "\n".join(f"- {i.reply}" for i in config.intents if i.reply)
    system_prompt = f"{config.llm_system_prompt}\n\nInformações disponíveis:\n{context}"

    payload = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None
