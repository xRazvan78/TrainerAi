"""
LLM service — streams guidance from Mistral AI.
Uses the OpenAI-compatible /v1/chat/completions endpoint with httpx async streaming.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.config import get_settings


_SYSTEM_PROMPT = """You are an AutoCAD training assistant embedded in a transparent overlay.
Output ONLY the guidance text — 2 to 4 sentences maximum.
No preamble, no reasoning, no bullet points, no critique, no self-analysis.
Start your response immediately with the first word of the guidance.
Use AutoCAD terminology. Tell the user what to do next — never repeat what they just did."""


def _build_user_prompt(
    command_text: str,
    active_tool: str,
    context_docs: list[str],
    command_sequence: list[str],
) -> str:
    context_block = "\n---\n".join(context_docs) if context_docs else "No relevant docs found."
    history = ", ".join(command_sequence[-5:]) if command_sequence else "none"
    return (
        f"Active tool: {active_tool or 'UNKNOWN'}\n"
        f"Last command: {command_text}\n"
        f"Recent command history: {history}\n\n"
        f"Relevant knowledge:\n{context_block}\n\n"
        f"What should the user do next?"
    )


async def stream_guidance(
    command_text: str,
    active_tool: str,
    context_docs: list[str],
    command_sequence: list[str],
) -> AsyncIterator[str]:
    settings = get_settings()
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(
                    command_text, active_tool, context_docs, command_sequence
                ),
            },
        ],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    yield token


async def generate_guidance(
    command_text: str,
    active_tool: str,
    context_docs: list[str],
    command_sequence: list[str],
) -> str:
    parts: list[str] = []
    async for token in stream_guidance(
        command_text, active_tool, context_docs, command_sequence
    ):
        parts.append(token)
    return "".join(parts)
