# Phase C — Qwen 3.5 LLM Integration + WebSocket Streaming

**Prerequisite for**: Phase F (full pipeline connection)  
**Depends on**: Phase A (Docker stack running)  
**Estimated effort**: 3–5 hours  
**Outside VS Code work**: Minor (verify Docker Model Runner is accessible)

---

## Goal

Connect the FastAPI backend to the locally-running Qwen model via Ollama's REST API. Add a WebSocket endpoint that the Tauri overlay can subscribe to for receiving streamed guidance token-by-token. Wire LLM inference into the command pipeline so every processed command results in real AI-generated guidance text.

---

## Architecture of This Phase

```
POST /api/command
      │
      ▼ (background task, non-blocking)
command_pipeline_service.run_week2_command_pipeline()
      │
      ├─ session_state_service     (already done)
      ├─ rag_service               (already done)
      ├─ llm_service.generate()    ← NEW — calls Docker Model Runner
      │       │
      │       └─ streams tokens → WebSocket broadcast
      └─ feedback_logger           (already done)

GET/WS /api/guidance/ws/{session_id}   ← NEW endpoint
      │ streams tokens as they arrive from Docker Model Runner
      ▼
Tauri overlay (Phase F)
```

---

## In VS Code — Files to Create/Modify

### 1. New file: `trainerAI_backend/app/services/llm_service.py`

```python
"""
LLM service — streams guidance from Docker Desktop Model Runner (Qwen 3.5).
Uses the OpenAI-compatible /v1/chat/completions endpoint with httpx async streaming.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List

import httpx

from app.config import settings


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
    """
    Yields guidance tokens one by one as they arrive from Docker Model Runner.
    Uses the OpenAI-compatible SSE streaming format (data: {...} lines).
    Raises httpx.HTTPError on connection failure.
    """
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
        "temperature": 0.3,   # low temp for factual, consistent guidance
        "max_tokens": 256,    # cap output to ~200 words
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
                chunk = json.loads(data)
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
    """Non-streaming version — returns the full response as a single string."""
    parts: List[str] = []
    async for token in stream_guidance(
        command_text, active_tool, context_docs, command_sequence
    ):
        parts.append(token)
    return "".join(parts)
```

---

### 2. Update `trainerAI_backend/app/config.py`

Add two new settings fields:

```python
docker_model_runner_url: str = "http://localhost:12434/engines/llama.cpp/v1"
llm_model: str = "ai/qwen3.5:35B-A3B-Q4_K_M"
```

---

### 3. New file: `trainerAI_backend/app/routers/guidance.py`

This adds the WebSocket endpoint the Tauri overlay will connect to:

```python
"""
WebSocket endpoint for streaming AI guidance to the overlay client.
One connection per session_id. Guidance is pushed as tokens arrive from Docker Model Runner.
"""
from __future__ import annotations

import asyncio
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/guidance", tags=["guidance"])

# In-memory registry: session_id → WebSocket
# Sufficient for a single-user desktop app (one overlay, one session at a time)
_active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/{session_id}")
async def guidance_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    _active_connections[session_id] = websocket
    try:
        # Keep the connection open; client sends pings to keep it alive
        while True:
            await asyncio.sleep(30)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        _active_connections.pop(session_id, None)


async def broadcast_token(session_id: str, token: str) -> None:
    """Push a single token to the connected overlay for this session."""
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text(token)
    except Exception:
        _active_connections.pop(session_id, None)


async def broadcast_done(session_id: str) -> None:
    """Signal to the overlay that the current guidance stream is complete."""
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_text('{"type":"done"}')
    except Exception:
        _active_connections.pop(session_id, None)
```

---

### 4. Update `trainerAI_backend/app/services/command_pipeline_service.py`

Wire LLM streaming into the existing pipeline after RAG retrieval:

```python
# At the end of run_week2_command_pipeline(), after rag_service call:

from app.services.llm_service import stream_guidance
from app.routers.guidance import broadcast_token, broadcast_done

context_texts = [doc.get("content", "") for doc in retrieved_docs]
session_snapshot = context_packet.session_snapshot

async for token in stream_guidance(
    command_text=context_packet.command_text,
    active_tool=session_snapshot.active_tool,
    context_docs=context_texts,
    command_sequence=session_snapshot.command_sequence,
):
    await broadcast_token(session_snapshot.session_id, token)

await broadcast_done(session_snapshot.session_id)
```

---

### 5. Register the new router in `trainerAI_backend/app/main.py`

```python
from app.routers import guidance
app.include_router(guidance.router)
```

---

### 6. Update `requirements.txt`

Add:

```
httpx >= 0.27.0
```

---

## Outside VS Code — Verify Docker Model Runner Serves Correctly

Before testing the backend endpoint:

```powershell
# Non-streaming test
$body = @{
    model = "ai/qwen3.5:35B-A3B-Q4_K_M"
    messages = @(@{ role = "user"; content = "In AutoCAD, what does the LINE command do?" })
    stream = $false
    max_tokens = 100
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
    -Uri http://localhost:12434/engines/llama.cpp/v1/chat/completions `
    -Body $body `
    -ContentType "application/json"
```

The response will have `choices[0].message.content` with generated text. This confirms the model is loaded and the OpenAI-compatible API is working.

---

## Testing the WebSocket Endpoint

With the backend running, use a simple Python WebSocket client to verify streaming:

```python
# test_ws.py (run from project root, not in pytest)
import asyncio
import websockets
import httpx

SESSION_ID = "test-session-001"

async def test():
    # First, ensure the session exists
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8000/db/sessions", json={
            "session_id": SESSION_ID,
            "skill_score": 0.5,
            "verbosity_level": "medium",
        })

    # Connect to WebSocket
    async with websockets.connect(f"ws://localhost:8000/api/guidance/ws/{SESSION_ID}") as ws:
        # Send a command to trigger the pipeline
        async with httpx.AsyncClient() as client:
            await client.post("http://localhost:8000/api/command", json={
                "text": "LINE",
                "timestamp": "2026-04-23T12:00:00Z",
                "session_id": SESSION_ID,
            })

        # Read streaming tokens
        async for msg in ws:
            print(msg, end="", flush=True)
            if '"type":"done"' in msg:
                break

asyncio.run(test())
```

---

## Prompt Engineering Notes

The system prompt in `llm_service.py` is intentionally minimal. Tuning priorities:

1. **Brevity**: 2–4 sentences max. The overlay is small.
2. **Actionability**: "Next, type FILLET and press Enter" not "The FILLET command rounds corners."
3. **Temperature 0.3**: Lower temperature reduces hallucinated command names.

The `num_predict: 256` cap (≈ 200 words) prevents the model from writing essays in the overlay.

---

## Acceptance Criteria

- [ ] `GET http://localhost:8000/docs` shows the `/api/guidance/ws/{session_id}` WebSocket endpoint
- [ ] POSTing to `/api/command` results in tokens appearing on the connected WebSocket within 2–5 seconds
- [ ] The guidance text is coherent and AutoCAD-relevant (not hallucinated)
- [ ] WebSocket connection survives idle for 60+ seconds (ping keepalive works)
- [ ] Backend does not crash or hang when Ollama is unreachable (exception handled gracefully in `safe_run_week2_command_pipeline`)
