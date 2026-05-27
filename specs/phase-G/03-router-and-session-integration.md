# Phase G.3: Router & Session-State Integration

## Overview

Plug `analyse_frame` into the two existing seams: the perception router (to enrich incoming frames with detected elements before persistence) and the session-state service (to override the active tool from OCR'd command-line text). Both edits are intentionally minimal — the heavy lifting is done by code that already exists.

## Prerequisites

- G.2 complete: `app/services/perception_service.py` exists and `analyse_frame` is importable.
- Existing perception ingestion works end-to-end (Phase E/F).

## Goals

- `POST /api/perception/state` runs `analyse_frame` when `frame_b64` is present and the client did not pre-populate `elements`, then persists the enriched payload (single JSONB row, single write).
- `session_state_service.update_session_from_command()` consults the latest persisted perception state; if it contains a `command_line` element with non-empty `text`, the active tool is derived from that OCR text instead of from the typed command.
- No new endpoints. No new database columns. No new request fields.

## Technical Design

### Router patch — `trainerAI_backend/app/routers/perception.py`

Add an import near the top:

```python
import asyncio
from app.services.perception_service import analyse_frame
```

Inside the `POST /api/perception/state` handler (currently around lines 17–46), **before** the existing `crud.create_perception_state(...)` call, add:

```python
if payload.frame_b64 and not payload.elements:
    detected = await asyncio.to_thread(analyse_frame, payload.frame_b64)
    if detected:
        payload = payload.model_copy(update={"elements": detected})
```

Decisions baked in:

- **Run only when `frame_b64` is present AND `elements` is empty.** Forward-compatible with future client-side detection: if the overlay ever ships its own YOLO, it can pre-populate `elements` and the server defers to it. No flag, no config — the `elements` field is its own switch.
- **`asyncio.to_thread`.** Keeps the event loop free; matches the spec snippet at `specs/phase-G-autocad-detection.md:266`. The capture loop's aHash dedup already throttles the call rate well below 2 Hz on a typical drawing session.
- **`payload.model_copy(update=...)`.** Pydantic v2 idiomatic; preserves all other fields (`session_id`, `timestamp`, `source`, `frame_hash`, `frame_b64`) unchanged.
- **Do not persist twice.** The enriched `payload` is what gets passed to `crud.create_perception_state(...)`; there is exactly one JSONB row per request, same as today.
- **Empty `detected` → no copy.** Preserves the original payload (with empty `elements`) so the perception row is still written and the capture cadence remains observable in the DB.

### Session-state patch — `trainerAI_backend/app/services/session_state_service.py`

Add a helper next to `_extract_active_tool()` (currently at line 13):

```python
def _extract_active_tool_from_perception(perception_state: dict | None) -> str | None:
    """Return the OCR'd active AutoCAD command, or None if not available."""
    if not perception_state:
        return None
    for el in perception_state.get("elements", []):
        if el.get("label") != "command_line":
            continue
        text = (el.get("text") or "").strip().upper()
        if not text:
            continue
        text = text.removeprefix("COMMAND:").strip()
        parts = text.split()
        if parts:
            return parts[0]
    return None
```

Then in `update_session_from_command()` (currently at line 46), after the existing `active_tool = _extract_active_tool(command_text)` line, fetch the latest perception state and override when a perception-derived tool is available:

```python
active_tool = _extract_active_tool(command_text)
latest_perception_row = await crud.get_latest_perception_state(pool, session_id)
perception_payload = (
    latest_perception_row["payload"] if latest_perception_row else None
)
perception_tool = _extract_active_tool_from_perception(perception_payload)
if perception_tool:
    active_tool = perception_tool
```

`crud.get_latest_perception_state` is the same call already made by `build_context_packet_foundation()` at `session_state_service.py:83` — confirmed to return `None` when no perception exists for the session, and a row mapping (with `"payload"` key holding the JSONB-decoded dict) otherwise.

Decisions baked in:

- **Perception wins when present and non-empty.** Typed command text is the fallback. Rationale: in the target deployment, the user types into AutoCAD's command line and the overlay learns about it via OCR, not via `/api/command`. The `/api/command` body's command text is at best a hint and at worst stale.
- **"Latest" means latest by `observed_at`.** Trusting the existing `get_latest_perception_state` semantics; do not add an age check in this phase. The Phase E aHash dedup means consecutive identical perceptions are not re-persisted, so "latest" is the freshest meaningful state.
- **`removeprefix("COMMAND:")` only after uppercase.** Handles `Command:`, `COMMAND:`, `command:` uniformly.
- **First whitespace-delimited token.** Matches `_extract_active_tool()`'s existing behaviour for command-text parsing. Multi-word AutoCAD commands (`HATCHEDIT`, `LIST`, etc.) are still single tokens.

### What this sub-phase does **not** do

- Does not change the response shape of `/api/perception/state`.
- Does not change the LLM prompt builder. `build_context_packet_foundation()` already includes the persisted perception payload in the context packet; enriched `elements` flow through for free.
- Does not change `_extract_active_tool()` or its existing callers.

## Implementation Steps

1. Edit `trainerAI_backend/app/routers/perception.py`:
   - Add `import asyncio` if not present.
   - Add `from app.services.perception_service import analyse_frame`.
   - Insert the inference + `model_copy` block before the existing `crud.create_perception_state(...)` call.

2. Edit `trainerAI_backend/app/services/session_state_service.py`:
   - Add the new `_extract_active_tool_from_perception` helper next to `_extract_active_tool`.
   - In `update_session_from_command`, fetch the latest perception state and apply the override.

3. Run the existing perception API test suite to confirm no regression:
   ```powershell
   cd trainerAI_backend
   pytest tests/test_perception_api.py -v
   ```
   All existing tests must still pass (they POST without `frame_b64`, so the new code path is not triggered).

4. Run the session-state tests:
   ```powershell
   pytest tests/test_session_state_service.py -v
   ```
   (If that file does not exist, the relevant session-state coverage may live in `tests/test_command_api.py` — run that too.)

## File & Directory Changes

| Path | Change | Notes |
|---|---|---|
| `trainerAI_backend/app/routers/perception.py` | Modify | Two imports + a four-line inference block. |
| `trainerAI_backend/app/services/session_state_service.py` | Modify | New helper function + a four-line override in `update_session_from_command`. |

## Testing & Validation

New tests are written in G.4. For this sub-phase, the regression checks (steps 3–4 above) are the bar.

## Edge Cases & Risks

- **`frame_b64` present but `elements` also non-empty.** Skipped — client's elements win. This is the future-compat hook; today no client does this.
- **`analyse_frame` raises despite its internal safety net.** Currently impossible (every internal failure mode returns `[]`), but if it ever did, the `asyncio.to_thread` would surface it and the request would 500. Acceptable — defence-in-depth in the router would be premature.
- **`get_latest_perception_state` returns a stale row.** A user might switch tools faster than the 500 ms capture cadence. Acceptable for the MVP: at worst the LLM sees the prior tool for one cycle. If this becomes a problem, the override can be gated on `observed_at` being within the last N seconds.
- **No perception ever recorded for the session.** `get_latest_perception_state` returns `None`; the override is skipped; `active_tool` falls back to the typed-command extraction. Already covered by the `if perception_tool:` guard.
- **Concurrent `POST /api/command` and `POST /api/perception/state`.** Race is benign: whichever lands first wins, and the next cycle's `update_session_from_command` will see the newer perception row.

## Notes

- The router change is intentionally on the **request path**, not in a post-persist hook. Persisting the raw payload first and then enriching would require a second DB write per frame at 2 Hz; the inline approach pays a latency tax but stays single-write.
- If a future sub-phase wants to background the inference and persist twice, the change is local: split the handler into "persist raw" and "schedule enrichment" and add an `enriched_at` column. Out of scope here.
