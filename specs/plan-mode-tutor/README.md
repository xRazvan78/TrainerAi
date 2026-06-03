# Plan Mode (Goal-Driven Tutor) — Project Overview

## Summary

TrainerAI today is **reactive**: the overlay captures the AutoCAD screen, perception detects the
active tool, and `command_pipeline_service` streams a short 2–4 sentence explanation of *what the user
is currently doing*. It never tells the user *what to build* or *how to get there*.

This project adds a second, **goal-driven** interaction mode — **Plan Mode** (a tutor) — that coexists
with the existing reactive guidance:

1. The user clicks a **Plan** button in the overlay, opening a chat panel.
2. The user describes what they want to build ("a hexagonal bolt", "a simple floor plan").
3. The backend retrieves relevant knowledge from the pgvector DB (RAG) and the LLM produces an
   **ordered, structured plan** — each step is an instruction plus the AutoCAD command it expects
   (`expected_tool`).
4. The overlay shows the plan as a live checklist and guides the user step-by-step.
5. **Progress tracking is hybrid**: the existing perception pipeline auto-advances a step when it
   detects the step's `expected_tool` on screen; the user can also click **Next** or type in chat.

## Goals & success criteria

- A user can toggle Plan Mode in the overlay, type a build goal, and receive a coherent ordered plan
  grounded in the knowledge base.
- Each plan step carries an `expected_tool` (AutoCAD command) used for automatic progress tracking.
- While a plan is active, performing the expected command in AutoCAD **auto-advances** the plan; the
  **Next** button and chat also advance it (hybrid).
- The user can chat with the tutor about the plan (follow-up questions, refinement).
- Reactive guidance keeps working unchanged when no plan is active, and is suppressed while a plan is
  active (to avoid double messaging).
- Backend unit tests cover plan state transitions and plan generation parsing; an end-to-end manual run
  demonstrates auto-advance.

## Confirmed decisions

| Decision | Choice | Implication |
|---|---|---|
| Progress tracking | **Hybrid** (perception auto-advance + manual Next/chat) | Hook into `perception.py`; add manual advance endpoint + button |
| V1 scope | **Full** — chat + plan generation + live tracking | All 5 phases in scope |
| Knowledge grounding | **RAG-grounded + LLM fill** | Plan prompt allows general AutoCAD knowledge to fill gaps |

## High-level architecture

A dedicated Plan Mode pipeline runs **parallel** to the reactive one, reusing existing infrastructure.
A **second WebSocket** (`/api/plan/ws/{session_id}`) carries a typed JSON protocol (chat tokens, full
plan, step-advance, done) so Plan Mode never interferes with the reactive guidance WS.

```
Overlay "Plan" toggle ──► POST /api/plan/create {session_id, goal}
   └─► plan_service.generate_plan()
         ├─ rag_service.retrieve_for_query()      (new thin helper, grounding)
         └─ llm_service.generate_plan_json()       (new, JSON output)
   └─► plan stored in-memory per session, pushed over Plan WS

Overlay chat input ──► POST /api/plan/message {session_id, text}
   └─► plan_service.chat() ─► llm_service.stream_chat()   (new, multi-turn)
         └─► plan_broadcaster streams tokens over Plan WS

AutoCAD screen ──► (existing) POST /api/perception/state
   └─► perception.py: if a plan is active, compare detected active_tool to the current step's
       expected_tool ─► plan_service.try_advance() ─► push step-advance over Plan WS
       (reactive guidance is suppressed while a plan is active)

Manual: POST /api/plan/advance   /   POST /api/plan/clear
```

## Tech stack & dependencies

No new third-party dependencies are required. Everything reuses what already ships:

- **Backend:** FastAPI, asyncpg, pydantic, httpx (Mistral SSE), sentence-transformers / pgvector
  (RAG). Mistral's `response_format: {"type":"json_object"}` is used for structured plan output.
- **Overlay:** Tauri + Dioxus (Rust), `reqwest` (HTTP), `tokio-tungstenite` (WS), the existing
  `js_sys::eval` JS-inbox bridge between Tauri events and Dioxus signals.

## Phase overview

| Phase | File | Purpose |
|---|---|---|
| 1 | `phase-1-backend-plan-core.md` | Plan models, in-memory `plan_service`, new LLM functions (`generate_plan_json`, `stream_chat`), RAG query helper |
| 2 | `phase-2-backend-router-ws-perception.md` | `plan_broadcaster`, `/api/plan/*` router + Plan WS, perception auto-advance hook, router registration |
| 3 | `phase-3-overlay-tauri.md` | Tauri commands (`plan_create/message/advance/clear`), Plan WS client, `lib.rs` wiring |
| 4 | `phase-4-overlay-dioxus-ui.md` | Dioxus Plan panel: chat transcript, live checklist, input/Send/Next, event intake |
| 5 | `phase-5-tests-verification.md` | Backend unit/API tests, end-to-end manual validation, graph upkeep |

## Assumptions & constraints

- Single-developer workstation: per-session plan state may live **in memory** (mirrors the existing
  `guidance_trigger_service` pattern); no DB persistence of plans required for v1.
- `session_id` comes from the `SESSION_ID` env var on the overlay side (default `default-session`),
  consistent with the rest of the app.
- The overlay only talks to `localhost` (enforced by the existing WS client guard).
- The 384-dim embedding model and pgvector schema are unchanged.

## Key risk to watch

The current corpus is *video-transcript chunks about individual commands*, not whole-object
procedures. Plan quality depends on the LLM stitching command-level knowledge into a coherent sequence.
The RAG-grounded + LLM-fill choice mitigates this — **validate plan quality early** (after Phases 1–2)
on a few real goals before investing in UI polish. If plans are weak, the fix is corpus ingestion, not
code.

## Glossary

- **Reactive guidance** — the existing flow: screen capture → tool detection → short explanation.
- **Plan Mode / Tutor** — the new flow: goal → structured plan → step-by-step guidance + tracking.
- **`expected_tool`** — the AutoCAD command a plan step expects (e.g. `POLYGON`), used to match against
  the perception-detected `active_tool` for auto-advance.
- **Plan WS** — the dedicated WebSocket `/api/plan/ws/{session_id}` with a typed JSON protocol.
