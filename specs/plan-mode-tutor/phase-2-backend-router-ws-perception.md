# Phase 2: Backend — Router, Plan WebSocket, Perception Hook

## Overview

This phase exposes the Phase 1 core over HTTP/WS and wires automatic progress tracking. It adds a
dedicated Plan broadcaster + WebSocket with a **typed** JSON protocol, the `/api/plan/*` REST
endpoints, registration in `main.py`, and the single hook in the existing perception router that
auto-advances an active plan. After this phase the backend is fully usable via `wscat` + `curl`.

## Prerequisites

- Phase 1 complete (`plan_models.py`, `plan_service.py`, `llm_service` additions, `rag_service.retrieve_for_query`).
- Familiarity with the existing `app/routers/guidance.py` (WS structure) and `app/routers/command.py`
  (202-accepted background-task pattern) — both are cloned here.

## Goals

- `plan_broadcaster.py` streams typed messages to a per-session Plan WebSocket.
- `app/routers/plan.py` exposes `WS /api/plan/ws/{session_id}`, `POST /api/plan/create`,
  `POST /api/plan/message`, `POST /api/plan/advance`, `POST /api/plan/clear`.
- `main.py` registers the plan router.
- `perception.py` auto-advances an active plan on tool match and suppresses reactive guidance while a
  plan is active.

## Technical Design

### Broadcaster — `app/services/plan_broadcaster.py`

Parallel to `app/services/ws_broadcaster.py` with its **own** `_active_connections` registry (so the
guidance WS and plan WS never collide). Typed protocol (all `send_text(json.dumps(...))`):

| Function | Wire message |
|---|---|
| `broadcast_chat_token(session_id, token)` | `{"type":"token","content": token}` |
| `broadcast_plan(session_id, plan)` | `{"type":"plan","plan": <plan dict>}` |
| `broadcast_step(session_id, plan)` | `{"type":"step","current_index": n,"plan": <plan dict>}` |
| `broadcast_done(session_id)` | `{"type":"done"}` |

`<plan dict>` = `Plan.model_dump()` (steps with index/instruction/expected_tool/status +
current_index + goal). Copy the safe-send + pop-on-failure behavior from `ws_broadcaster`. Provide
`register(session_id, ws)` / `unregister(session_id, ws)` or reuse the same `_active_connections`
access style as the guidance broadcaster — match whichever idiom the existing code uses.

### Router — `app/routers/plan.py`

Clone the structure of `guidance.py` (WS + ping loop) and `command.py` (202 + `asyncio.create_task`).
Get the pool via `getattr(request.app.state, "db_pool", None)` like the existing routers.

```python
router = APIRouter(prefix="/api/plan", tags=["plan"])

@router.websocket("/ws/{session_id}")
async def plan_ws(websocket, session_id): ...
    # accept; close any existing conn for session; register in plan_broadcaster;
    # ping loop every ~20-30s ({"type":"ping"}); unregister in finally. (copy guidance.py)

@router.post("/create", status_code=202)
async def plan_create(payload: PlanCreateRequest, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    asyncio.create_task(_run_create(pool, payload.session_id, payload.goal))
    return {"status": "accepted", "session_id": payload.session_id}

@router.post("/message", status_code=202)
async def plan_message(payload: PlanMessageRequest, request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    asyncio.create_task(_run_message(pool, payload.session_id, payload.text))
    return {"status": "accepted", "session_id": payload.session_id}

@router.post("/advance")
async def plan_advance(payload: PlanAdvanceRequest):
    plan = plan_service.advance_manual(payload.session_id)
    if plan: await plan_broadcaster.broadcast_step(payload.session_id, plan)
    return {"status": "ok"}

@router.post("/clear")
async def plan_clear(payload: PlanAdvanceRequest):
    plan_service.clear(payload.session_id)
    return {"status": "ok"}
```

Background coroutines:

```python
async def _run_create(pool, session_id, goal):
    plan = await plan_service.generate_plan(pool, session_id, goal)
    await plan_broadcaster.broadcast_plan(session_id, plan)

async def _run_message(pool, session_id, text):
    async for token in plan_service.chat(pool, session_id, text):
        await plan_broadcaster.broadcast_chat_token(session_id, token)
    await plan_broadcaster.broadcast_done(session_id)
```

Wrap `_run_create` / `_run_message` in a try/except that logs and (best-effort) broadcasts a `done`
on failure, mirroring `safe_run_week2_command_pipeline`'s defensive style.

### Registration — `app/main.py`

Add alongside the existing `app.include_router(...)` calls:

```python
from app.routers.plan import router as plan_router
...
app.include_router(plan_router)   # /api/plan/*
```

### Perception hook — `app/routers/perception.py`

Locate where `active_tool` is determined and the existing
`guidance_trigger_service.should_trigger(...)` decision is made. Insert a plan branch **before** the
reactive trigger:

```python
if plan_service.has_active_plan(session_id):
    advanced = plan_service.try_advance(session_id, active_tool)
    if advanced is not None:
        await plan_broadcaster.broadcast_step(session_id, advanced)
    # Plan Mode owns this session: skip reactive guidance entirely.
    return persisted_response   # whatever the handler already returns on the no-guidance path
# ... existing reactive guidance path unchanged ...
```

Notes:
- Only this branch is added; the existing reactive path is untouched for sessions without a plan.
- Suppressing reactive guidance while a plan is active is intentional (avoids double messaging). When
  the plan completes, `has_active_plan` returns False and reactive guidance resumes automatically.
- Keep the perception persistence (DB write) before this branch so frames are still recorded.

## Implementation Steps

1. Create `app/services/plan_broadcaster.py` (clone `ws_broadcaster.py`, swap to typed messages, own registry).
2. Create `app/routers/plan.py` with the WS endpoint, four REST endpoints, and the two background coroutines.
3. Register `plan_router` in `app/main.py`.
4. Edit `app/routers/perception.py` to add the plan auto-advance branch + reactive suppression.
5. Start the server and smoke test (see Testing).

## File & Directory Changes

- **New:** `app/services/plan_broadcaster.py` — typed Plan WS broadcaster + registry.
- **New:** `app/routers/plan.py` — Plan WS + REST endpoints + background runners.
- **Modified:** `app/main.py` — register `plan_router`.
- **Modified:** `app/routers/perception.py` — plan auto-advance hook + reactive suppression branch.

## Testing & Validation

Manual smoke (full automated tests in Phase 5):

1. `cd trainerAI_backend; uvicorn app.main:app --reload`.
2. In one terminal: `wscat -c ws://localhost:8000/api/plan/ws/default-session`.
3. In another (PowerShell):
   ```powershell
   Invoke-RestMethod -Method Post http://localhost:8000/api/plan/create `
     -Body (@{session_id="default-session"; goal="draw a hexagon"} | ConvertTo-Json) `
     -ContentType application/json
   ```
   → expect a `{"type":"plan", "plan":{...steps...}}` message in the wscat session.
4. `Invoke-RestMethod -Method Post .../api/plan/message -Body (@{session_id="default-session"; text="why POLYGON?"} | ConvertTo-Json) -ContentType application/json`
   → expect streamed `{"type":"token",...}` then `{"type":"done"}`.
5. `.../api/plan/advance` → expect `{"type":"step",...}` with incremented `current_index`.
6. OpenAPI check: `GET http://localhost:8000/docs` lists the four `/api/plan/*` routes.

## Edge Cases & Risks

- **No WS connected when create/message runs** → broadcaster pops/no-ops silently (same as guidance);
  acceptable. The overlay connects on startup so this is mainly a CLI-testing concern.
- **Concurrent create + message** → keep it simple; messages assume a plan exists. If `chat` is called
  before a plan exists, treat the text as a goal (call `generate_plan`) — decide in Phase 1 `chat`
  contract; document the chosen behavior here.
- **Perception fires rapidly** → `try_advance` only advances on an actual tool match, and marking a
  step done is idempotent per step, so duplicate frames won't skip steps.
- **Pool is None** (DB down) → background runners catch and broadcast `done`; surface a server log.

## Notes

- Reused: `guidance.py` WS scaffold, `command.py` 202+background-task pattern, `ws_broadcaster` safe-send
  idiom, `request.app.state.db_pool` access.
- Ping interval/format should match the overlay's WS client expectations (Phase 3 ignores `ping`).
