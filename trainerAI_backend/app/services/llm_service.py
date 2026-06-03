"""
LLM service — streams guidance from Mistral AI.
Uses the OpenAI-compatible /v1/chat/completions endpoint with httpx async streaming.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

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


_PLAN_SYSTEM_PROMPT = """You are an expert AutoCAD instructor. Given a build goal and reference
knowledge, produce an ordered, concrete plan to accomplish it in AutoCAD.
Ground the plan in the provided knowledge; you MAY use your general AutoCAD knowledge to fill gaps.
Return ONLY JSON of the form:
{"steps": [{"instruction": "<short imperative action, max ~8 words>", "detail": "<1-2 sentences explaining HOW: the exact command flow, key parameters/values to type, and where to click>", "expected_tool": "<primary AutoCAD command, e.g. LINE, POLYGON, FILLET, or null>"}]}
The instruction is a terse checklist line; put all the how-to in detail. Be specific in detail
(coordinates, dimensions, option keywords, Enter presses). 4–8 steps. Use uppercase AutoCAD command names.
Keep one continuous action that uses a single command as ONE step (describe the repetitions in detail) —
do not split it across several steps. Only put the same command in consecutive steps when they are
genuinely separate operations. Prefer giving adjacent steps different expected_tool values where natural."""

_CHAT_SYSTEM_PROMPT = """You are an AutoCAD tutor guiding a user through an active build plan.
Be concise and practical. Reference the current step. Answer follow-up questions, and if asked,
suggest how to adjust the plan. Use AutoCAD terminology."""


async def generate_plan_json(goal: str, context_docs: list[str]) -> list[dict]:
    settings = get_settings()
    context_block = "\n---\n".join(context_docs) if context_docs else "No relevant docs found."
    user_content = f"Goal: {goal}\n\nReference knowledge:\n{context_block}"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed.get("steps", [])
    except Exception:
        logger.exception("generate_plan_json failed for goal %r", goal)
        return []


async def stream_chat(
    messages: list[dict],
    system_prompt: str,
    context_docs: list[str],
) -> AsyncIterator[str]:
    settings = get_settings()
    context_block = "\n---\n".join(context_docs) if context_docs else ""
    system_content = system_prompt
    if context_block:
        system_content = f"{system_prompt}\n\nContext:\n{context_block}"
    full_messages = [{"role": "system", "content": system_content}, *messages]
    payload = {
        "model": settings.llm_model,
        "messages": full_messages,
        "stream": True,
        "temperature": 0.4,
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
