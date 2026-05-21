# Sub-phase C.4 — Wire LLM Streaming into the Command Pipeline

## Overview

Connect the LLM service (C.2) and the WebSocket router (C.3) into the existing background command pipeline (`run_week2_command_pipeline`). After RAG retrieval finishes, the pipeline streams Qwen tokens out to the connected overlay WebSocket for the current session, then signals completion. This is the integration step that makes Phase C visible end-to-end.

## Prerequisites

- C.1, C.2, C.3 all complete and passing tests.
- Familiarity with `trainerAI_backend/app/services/command_pipeline_service.py` (small file, ~57 lines).

## Goals

- After RAG retrieval, `stream_guidance` is called and every yielded token is sent via `broadcast_token`.
- A terminal `broadcast_done` is sent after the stream completes.
- A failure inside the LLM call (e.g., Model Runner down) does **not** crash the background task — the existing `safe_run_week2_command_pipeline` wrapper catches `httpx.HTTPError` and returns silently.
- Feedback logging continues to run as an `asyncio.create_task` background job, unchanged.
- The existing pipeline test (`test_e2e_context_logging_with_perception_and_rag`) still passes after being updated to fake the new LLM and broadcast functions.

## Technical Design

### Insertion point in `command_pipeline_service.py`

Current flow (lines 13–35):

```
foundation = await build_context_packet_foundation(...)
retrieved_context = await safe_retrieve_context_documents(...)
asyncio.create_task(safe_persist_command_feedback(...))
```

After the change:

```
foundation = await build_context_packet_foundation(...)
retrieved_context = await safe_retrieve_context_documents(...)

# NEW: stream LLM guidance to the overlay
context_texts = [doc.get("content", "") for doc in retrieved_context]
session = foundation.session
async for token in stream_guidance(
    command_text=foundation.command_text,
    active_tool=session.active_tool,
    context_docs=context_texts,
    command_sequence=session.command_sequence,
):
    await broadcast_token(session.session_id, token)
await broadcast_done(session.session_id)

# unchanged: schedule feedback logging in the background
asyncio.create_task(safe_persist_command_feedback(...))
```

### Import block additions

At the top of `command_pipeline_service.py`:

```python
import httpx

from app.routers.guidance import broadcast_done, broadcast_token
from app.services.llm_service import stream_guidance
```

### Update `safe_run_week2_command_pipeline` exception tuple

Add `httpx.HTTPError` so a downed Model Runner doesn't crash the FastAPI background task:

```python
except (
    asyncpg.PostgresError,
    OSError,
    RuntimeError,
    asyncio.TimeoutError,
    ValueError,
    TypeError,
    httpx.HTTPError,
):
    return
```

### Design notes

- **Streaming runs *between* RAG retrieval and feedback logging**: the feedback logger only needs the retrieved context; it does not need the LLM output, so streaming need not block on its completion. Keeping the feedback log as a fire-and-forget `create_task` is the simplest correct ordering.
- **Why not stream and log in parallel?** The pipeline ordering is "produce guidance ASAP, persist context later" — a parallel layout would add complexity for no UX benefit (the WS client doesn't care about the feedback row).
- **Why `foundation.session`, not `context_packet.session_snapshot`?** The original Phase C spec used `context_packet.session_snapshot`, but the real attribute on `ContextPacketFoundation` is `.session: SessionSnapshot` — confirm by reading `app/models/context_models.py`.

## Implementation Steps

1. Open `trainerAI_backend/app/services/command_pipeline_service.py`.
2. Add the three new imports (`httpx`, `broadcast_*`, `stream_guidance`) at the top.
3. Between the existing `safe_retrieve_context_documents` call and the `asyncio.create_task(...)` for feedback logging, insert the streaming block from §Technical Design.
4. Add `httpx.HTTPError` to the exception tuple in `safe_run_week2_command_pipeline`.
5. Update `trainerAI_backend/tests/test_command_pipeline_service.py`:
   - Add `monkeypatch.setattr(command_pipeline_service, "stream_guidance", fake_stream_guidance)` where `fake_stream_guidance` is an `async def` returning an `AsyncIterator[str]` that yields `["Try ", "the ", "LINE ", "tool"]`.
   - Add `monkeypatch.setattr(command_pipeline_service, "broadcast_token", fake_broadcast_token)` and same for `broadcast_done`, each appending into a list in `captured`.
   - Assert the captured tokens equal `["Try ", "the ", "LINE ", "tool"]` and that `broadcast_done` was called exactly once with `"session-e2e"`.
6. Run `pytest tests/test_command_pipeline_service.py -v` and confirm pass.
7. Run the full backend test suite: `pytest tests/ -v`. Expect ~33 tests passing (27 existing + ~6 new from C.1/C.2/C.3/C.4).

## File & Directory Changes

| Path | Change |
|---|---|
| `trainerAI_backend/app/services/command_pipeline_service.py` | Add imports; insert streaming block; extend exception tuple. |
| `trainerAI_backend/tests/test_command_pipeline_service.py` | Update E2E test with stream/broadcast fakes and new assertions. |

## Testing & Validation

- `pytest tests/test_command_pipeline_service.py::test_e2e_context_logging_with_perception_and_rag -v` — passes with new assertions.
- `pytest tests/ -v` — full suite green.
- Quick import check: `python -c "from app.services.command_pipeline_service import run_week2_command_pipeline"` from `trainerAI_backend/` — no import errors.

End-to-end manual verification is deferred to C.5 (the acceptance phase).

## Edge Cases & Risks

- **No connected WS client**: `broadcast_token` is a no-op when nothing is connected. The pipeline still pays the LLM-inference cost (~1–3 s) for nothing. Acceptable for Phase C; an optimisation could check `_active_connections` before invoking the LLM, but that couples the service to the router's private state — defer.
- **LLM stream interrupted mid-way (network blip)**: `stream_guidance` raises an `httpx.HTTPError`; the outer `safe_run_week2_command_pipeline` swallows it. The WS client receives a partial response and no `done` marker — the overlay will need a client-side timeout to handle this in Phase F. Document the behaviour but do not fix it here.
- **Slow first token**: cold-load latency on the Model Runner can be 30–60 s. The `httpx` timeout is 60 s; longer than that and the pipeline aborts. Acceptable for development; production tuning is out of scope.
- **Feedback logger race**: `asyncio.create_task` is created *after* streaming finishes (vs. before, as in the original code). This is intentional — it ensures the feedback log captures the retrieved context even if the LLM streaming fails. Verify with the updated test that the feedback logger is still invoked exactly once.

## Notes

- Do **not** wrap the `async for token in stream_guidance(...)` block in its own try/except — let exceptions bubble to `safe_run_week2_command_pipeline`. A local try/except would silently swallow LLM failures without sending `broadcast_done`, leaving the overlay client hanging.
- After this sub-phase, the project should be functionally complete for Phase C. C.5 is verification only — no new code.
