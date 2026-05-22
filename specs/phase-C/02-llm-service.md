# Sub-phase C.2 — LLM Service (Qwen SSE Streaming Client)

## Overview

Implement `app/services/llm_service.py`: an async generator that POSTs to the Docker Model Runner's OpenAI-compatible `/chat/completions` endpoint with `stream=True`, parses the SSE response, and yields content tokens one at a time. Also expose a convenience `generate_guidance(...)` wrapper that buffers the full string for callers that don't want streaming.

This is the pure-Python core of Phase C — no FastAPI, no DB, no WebSocket. It is fully unit-testable by monkeypatching `httpx.AsyncClient`.

## Prerequisites

- C.1 complete: `httpx` installed, `get_settings()` exposes `docker_model_runner_url` and `llm_model`.
- Familiarity with the OpenAI Chat Completions streaming SSE format (`data: {json}` lines, terminated by `data: [DONE]`).

## Goals

- `stream_guidance(command_text, active_tool, context_docs, command_sequence) -> AsyncIterator[str]` yields tokens.
- `generate_guidance(...)` returns the full concatenated string.
- A focused unit test suite covers SSE parsing, prompt building, and the `[DONE]` sentinel.
- The module imports cleanly with no side effects (no HTTP at import time).

## Technical Design

### File: `trainerAI_backend/app/services/llm_service.py`

```python
"""
LLM service — streams guidance from Docker Desktop Model Runner (Qwen 3.5).
Uses the OpenAI-compatible /v1/chat/completions endpoint with httpx async streaming.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List

import httpx

from app.config import get_settings


_SYSTEM_PROMPT = """You are an AutoCAD training assistant embedded in a transparent overlay.
The user is currently working in AutoCAD. Based on their recent commands and retrieved knowledge,
provide brief, actionable guidance (2-4 sentences maximum).
Be direct. Use AutoCAD terminology. Never repeat what the user just did — tell them what to do next."""


def _build_user_prompt(
    command_text: str,
    active_tool: str,
    context_docs: List[str],
    command_sequence: List[str],
) -> str:
    context_block = "\n---\n".join(context_docs) if context_docs else "No relevant docs found."
    history = ", ".join(command_sequence[-5:]) if command_sequence else "none"
    return (
        f"Active tool: {active_tool}\n"
        f"Last command: {command_text}\n"
        f"Recent command history: {history}\n\n"
        f"Relevant knowledge:\n{context_block}\n\n"
        f"What should the user do next?"
    )


async def stream_guidance(
    command_text: str,
    active_tool: str,
    context_docs: List[str],
    command_sequence: List[str],
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
        "max_tokens": 256,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{settings.docker_model_runner_url}/chat/completions",
            json=payload,
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
                token = (
                    chunk.get("choices", [{}])[0]
                    .get("delta", {})
                    .get("content", "")
                )
                if token:
                    yield token


async def generate_guidance(
    command_text: str,
    active_tool: str,
    context_docs: List[str],
    command_sequence: List[str],
) -> str:
    parts: List[str] = []
    async for token in stream_guidance(
        command_text, active_tool, context_docs, command_sequence
    ):
        parts.append(token)
    return "".join(parts)
```

### Design notes

- **Timeout = 60 s**: covers cold-load Qwen latency on first request after the container starts. Subsequent requests are fast.
- **JSON parse failures are swallowed silently**: an occasional malformed keepalive line should not abort the stream.
- **`max_tokens=256`**: caps overlay output at roughly 200 words — guards against the model writing essays.
- **`temperature=0.3`**: low enough to reduce hallucinated AutoCAD command names but still allows minor variation.
- **No retry logic**: the caller (Phase C.4) treats LLM failures as "skip this turn" and continues; retries belong in a later phase.

## Implementation Steps

1. Create `trainerAI_backend/app/services/llm_service.py` with the contents above.
2. Create `trainerAI_backend/tests/test_llm_service.py` with the two tests described in §Testing.
3. Run `pytest tests/test_llm_service.py -v` and confirm both tests pass.
4. From `trainerAI_backend/`, run a quick smoke check (only if Docker Model Runner is running):
   ```bash
   python -c "import asyncio; from app.services.llm_service import generate_guidance; print(asyncio.run(generate_guidance('LINE', 'LINE', ['LINE draws straight segments.'], ['LINE'])))"
   ```
   Expected: a 2–4 sentence guidance string.

## File & Directory Changes

| Path | Change |
|---|---|
| `trainerAI_backend/app/services/llm_service.py` | NEW — streaming LLM client. |
| `trainerAI_backend/tests/test_llm_service.py` | NEW — unit tests for SSE parsing and prompt building. |

## Testing & Validation

Two unit tests, both fully offline:

### `test_stream_guidance_parses_sse_chunks`

Monkeypatch `httpx.AsyncClient` so `.stream(...)` returns a fake async context manager whose `.aiter_lines()` yields:

```
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: {"choices":[{"delta":{"content":" world"}}]}
data: {"choices":[{"delta":{}}]}      # no content key — should be skipped
(empty line)                          # should be skipped
data: not-json                        # malformed — should be skipped
data: [DONE]                          # terminates stream
data: {"choices":[{"delta":{"content":"never"}}]}  # after [DONE] — must not appear
```

Assert the collected list is `["Hello", " world"]` exactly.

### `test_build_user_prompt_includes_history_and_context`

Pure-function test (no monkeypatching needed):
- Call `_build_user_prompt("LINE 0,0 10,10", "LINE", ["Doc A", "Doc B"], ["MOVE", "COPY", "LINE"])`.
- Assert the returned string contains `"Active tool: LINE"`, `"Last command: LINE 0,0 10,10"`, `"MOVE, COPY, LINE"`, `"Doc A\n---\nDoc B"`.
- Re-call with empty `context_docs=[]` and empty `command_sequence=[]` and assert `"No relevant docs found."` and `"Recent command history: none"` both appear.

## Edge Cases & Risks

- **`raise_for_status()` propagates `httpx.HTTPStatusError`**: this is intentional — the pipeline wrapper (`safe_run_week2_command_pipeline`, modified in C.4) will catch it.
- **`aiter_lines` may return `None`-like or whitespace-only entries on some httpx versions**: the `if not line` guard covers this.
- **Server returns 200 with an error JSON instead of streaming SSE**: parser will skip non-`data:` lines and yield nothing. Acceptable behaviour for Phase C; surface as "no guidance" on the WS.
- **Cold-start latency**: first request after `docker compose up` can take 30–60 s while Qwen loads. Tests are mocked so this doesn't affect CI.

## Notes

- The `_SYSTEM_PROMPT` is intentionally minimal; future prompt tuning belongs in a separate ticket, not Phase C.
- Do not add `functools.lru_cache` to `stream_guidance` — it's an async generator and the cache would be meaningless. Caching responses is out of scope.
- Do not create an `httpx.AsyncClient` at module scope — the per-call `async with` is cheap and avoids loop-binding issues during tests.
