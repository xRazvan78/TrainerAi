# Phase 1: Backend — Plan Core (models, state service, LLM functions)

## Overview

This phase builds the backend "brain" of Plan Mode with **no HTTP/WS surface yet**: the data models, an
in-memory per-session plan state service, the new LLM calls (structured plan generation + multi-turn
chat), and a thin RAG helper for arbitrary query strings. It comes first because every later phase
(router, overlay) depends on these primitives, and they can be unit-tested in isolation.

## Prerequisites

- Working backend dev environment: `cd trainerAI_backend; pip install -r requirements.txt`.
- pgvector running (`docker compose up -d`) with the corpus ingested (needed only to exercise RAG; the
  pure state logic is testable without it).
- `LLM_API_KEY` set (Mistral) for live LLM calls; unit tests mock the HTTP layer.

## Goals

- `plan_models.py` defines `PlanStep`, `Plan`, `ChatMessage`, and the request models.
- `plan_service.py` holds per-session plans in memory and exposes generate / get / advance / clear /
  chat functions.
- `llm_service.py` gains `generate_plan_json()` (JSON output) and `stream_chat()` (multi-turn streaming)
  without altering existing `stream_guidance`.
- `rag_service.py` gains `retrieve_for_query()` for grounding on an arbitrary goal string.

## Technical Design

### Data models — `app/models/plan_models.py`

Follow the pydantic style in `app/models/command_models.py` and `app/models/context_models.py`.

```python
from typing import Literal
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class PlanStep(BaseModel):
    index: int
    instruction: str
    expected_tool: str | None = None          # AutoCAD command, normalized uppercase, e.g. "POLYGON"
    status: Literal["pending", "active", "done"] = "pending"

class Plan(BaseModel):
    session_id: str
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    current_index: int = 0
    messages: list[ChatMessage] = Field(default_factory=list)

# Request bodies (used by Phase 2 router; defined here to co-locate models)
class PlanCreateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)

class PlanMessageRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)

class PlanAdvanceRequest(BaseModel):
    session_id: str = Field(min_length=1)
```

> If `app/models/` does not exist as a package, place these next to the existing model modules
> (the explorer found `command_models.py` / `context_models.py`); match their actual location and the
> existing import style.

### State service — `app/services/plan_service.py`

Mirror the in-memory, never-evicted, per-session pattern used by
`app/services/guidance_trigger_service.py` (module-level dict; single-dev workstation).

```python
_plans: dict[str, Plan] = {}

def get_plan(session_id: str) -> Plan | None: ...
def has_active_plan(session_id: str) -> bool:
    plan = _plans.get(session_id)
    return plan is not None and plan.current_index < len(plan.steps)
def clear(session_id: str) -> None: _plans.pop(session_id, None)

def _normalize_tool(tool: str | None) -> str:
    return (tool or "").strip().upper()

async def generate_plan(pool, session_id: str, goal: str) -> Plan: ...
def try_advance(session_id: str, detected_tool: str | None) -> Plan | None: ...
def advance_manual(session_id: str) -> Plan | None: ...
async def chat(pool, session_id: str, text: str) -> AsyncIterator[str]: ...
```

Behavior contracts:

- **`generate_plan`**: retrieve grounding docs via `rag_service.retrieve_for_query(pool, goal)`; call
  `llm_service.generate_plan_json(goal, context_docs)`; build `PlanStep`s (index 0..n-1, normalize
  `expected_tool` via `_normalize_tool`); set step 0 `status="active"`, `current_index=0`; seed
  `messages` with the assistant's rendered plan summary; store in `_plans[session_id]`; return it.
- **`try_advance(session_id, detected_tool)`**: if no active plan → `None`. If
  `_normalize_tool(detected_tool) == current_step.expected_tool` (and `expected_tool` is non-empty),
  mark current step `done`, increment `current_index`, mark the new current step `active` (if any),
  return the updated plan. Otherwise return `None` (no change). This is the perception auto-advance path.
- **`advance_manual(session_id)`**: unconditionally mark current step `done`, increment, mark next
  `active`; return updated plan (or `None` if no active plan). Drives the **Next** button.
- **`chat(session_id, text)`**: append `ChatMessage(role="user", ...)`; build context from the current
  plan (goal, steps with statuses, current step) + recent messages; stream the assistant reply via
  `llm_service.stream_chat(...)`; accumulate and append `ChatMessage(role="assistant", ...)` at the
  end; yield tokens as they arrive.

### LLM functions — `app/services/llm_service.py`

Reuse the existing httpx + SSE streaming pattern in `stream_guidance` (same base URL, headers, model,
SSE `data:` parsing). **Do not modify `stream_guidance` / `generate_guidance`.**

New module constants:

```python
_PLAN_SYSTEM_PROMPT = """You are an expert AutoCAD instructor. Given a build goal and reference
knowledge, produce an ordered, concrete plan to accomplish it in AutoCAD.
Ground the plan in the provided knowledge; you MAY use your general AutoCAD knowledge to fill gaps.
Return ONLY JSON of the form:
{"steps": [{"instruction": "<one clear action>", "expected_tool": "<primary AutoCAD command, e.g. LINE, POLYGON, FILLET, or null>"}]}
Keep instructions short and actionable. 4–10 steps. Use uppercase AutoCAD command names."""

_CHAT_SYSTEM_PROMPT = """You are an AutoCAD tutor guiding a user through an active build plan.
Be concise and practical. Reference the current step. Answer follow-up questions, and if asked,
suggest how to adjust the plan. Use AutoCAD terminology."""
```

New functions:

```python
async def generate_plan_json(goal: str, context_docs: list[str]) -> list[dict]:
    """Non-streaming Mistral call with response_format={"type":"json_object"}.
    Returns the parsed list of step dicts ({"instruction","expected_tool"}).
    Robust parse: json.loads the message content; read obj["steps"]; on failure return []."""

async def stream_chat(
    messages: list[dict],          # [{"role","content"}, ...] conversation so far
    system_prompt: str,
    context_docs: list[str],
) -> AsyncIterator[str]:
    """Multi-turn streaming. Build the messages array as:
    [{"role":"system","content": system_prompt + rendered context_docs}, *messages].
    Same SSE handling as stream_guidance; yields delta.content tokens."""
```

Payload notes:
- `generate_plan_json`: `{"model": settings.llm_model, "messages":[system, user(goal+context)],
  "stream": False, "temperature": 0.3, "response_format": {"type":"json_object"}}`.
- `stream_chat`: `{"model": ..., "messages": [...], "stream": True, "temperature": 0.4,
  "max_tokens": 1024}`.

### RAG helper — `app/services/rag_service.py`

The existing `retrieve_context_documents(pool, foundation, ...)` requires a
`ContextPacketFoundation`. Add a thin helper for arbitrary query strings that reuses
`embedder_service.embed_text` and `crud.query_similar_embeddings` directly (the same two calls the
existing function makes internally):

```python
async def retrieve_for_query(
    pool,
    query_text: str,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,   # reuse existing module constant 0.72
    top_k: int = DEFAULT_TOP_K,                        # reuse existing 4
    token_budget: int = DEFAULT_TOKEN_BUDGET,         # reuse existing 1200
) -> list[dict[str, Any]]:
    query_embedding = embed_text(query_text)
    results = await crud.query_similar_embeddings(
        pool=pool, embedding=query_embedding, min_similarity=min_similarity, limit=top_k,
    )
    return _apply_token_budget(results, token_budget)   # reuse existing private helper
```

`plan_service.generate_plan` then does
`context_texts = [d.get("content","") for d in await retrieve_for_query(pool, goal)]`.

## Implementation Steps

1. Create `app/models/plan_models.py` with the models above (match the existing models' location/style).
2. Add `retrieve_for_query` to `rag_service.py`, reusing the existing constants and `_apply_token_budget`.
3. Add `_PLAN_SYSTEM_PROMPT`, `_CHAT_SYSTEM_PROMPT`, `generate_plan_json`, and `stream_chat` to
   `llm_service.py` (clone the existing httpx/SSE plumbing).
4. Create `app/services/plan_service.py` with the in-memory store and the functions/contracts above.
5. Sanity-check imports compile: `cd trainerAI_backend; python -c "import app.services.plan_service"`.

## File & Directory Changes

- **New:** `app/models/plan_models.py` — plan/chat/request models.
- **New:** `app/services/plan_service.py` — in-memory plan state + orchestration.
- **Modified:** `app/services/llm_service.py` — add `generate_plan_json`, `stream_chat`, two prompts.
- **Modified:** `app/services/rag_service.py` — add `retrieve_for_query`.

## Testing & Validation

- Unit-testable now (full tests live in Phase 5): import the module, build a `Plan` by hand, assert
  `try_advance` matches normalized tools and advances; `advance_manual` advances unconditionally;
  `clear` removes state; `has_active_plan` reflects completion.
- `generate_plan_json` parse path: feed a sample JSON string through the parser (mock httpx) and assert
  the step list shape.
- Compile check: `python -c "import app.services.plan_service, app.services.llm_service, app.services.rag_service"`.

## Edge Cases & Risks

- **LLM returns malformed JSON** → `generate_plan_json` must return `[]`; `generate_plan` should then
  produce a single fallback step ("Describe your goal in more detail") rather than an empty plan.
- **`expected_tool` null / free text** → store `None`; `try_advance` only auto-advances when
  `expected_tool` is non-empty, so such steps require the manual Next button.
- **Tool-name mismatch** between perception `active_tool` and LLM `expected_tool` formats → both pass
  through `_normalize_tool` (uppercase/strip). Exact-match in v1; fuzzy/alias matching is a follow-up.
- **Plan completed** (`current_index == len(steps)`) → `has_active_plan` returns False; perception hook
  (Phase 2) then stops auto-advancing and reactive guidance resumes.

## Notes

- Keep `plan_service` free of FastAPI imports so it stays unit-testable; the router (Phase 2) injects
  the asyncpg `pool`.
- Reused building blocks: `embedder_service.embed_text`, `crud.query_similar_embeddings`,
  `rag_service._apply_token_budget`, the `stream_guidance` httpx/SSE pattern, and the
  `guidance_trigger_service` module-dict pattern.
