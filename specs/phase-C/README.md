# Phase C — Qwen LLM Integration + WebSocket Streaming (Execution Plan)

This folder breaks Phase C (`specs/phase-C-qwen-llm-integration.md`) into five sequential sub-phases, each in its own file. The original spec remains the design reference; this folder is the runbook for the dev team.

## Why this exists

Phase D filled the `embeddings` table with real AutoCAD knowledge chunks, and the command pipeline today does session-state → RAG retrieval → feedback log — but it never calls the LLM. Every `POST /api/command` produces context but no actual guidance text, so the Tauri overlay has nothing to render. Phase C closes that gap: stream guidance from the locally-hosted Qwen 3.5 model (Docker Desktop Model Runner, OpenAI-compatible API at `http://localhost:12434/engines/llama.cpp/v1`) and expose it to the overlay via a per-session WebSocket. This is the prerequisite for Phase F (full pipeline wiring).

## Two reconciliations with the original spec

The dev team should be aware of these before starting — they change small details in `phase-C-qwen-llm-integration.md`:

1. **The pipeline service uses `foundation.session`, not `context_packet.session_snapshot`.** The spec's snippet in §4 references `context_packet.session_snapshot.active_tool` etc., but the actual model in `app/models/context_models.py` exposes `ContextPacketFoundation.session: SessionSnapshot`. Sub-phase **C.4** uses the real attribute path.
2. **`get_settings()` over a `settings` singleton import.** The spec's `from app.config import settings` is not the existing convention — `app/services/embedder_service.py` and `app/services/rag_service.py` both call `get_settings()` (the `lru_cache`-d factory). Sub-phases **C.1** and **C.2** follow that pattern.

## Sub-phase index

| # | File | Title | Owner suggestion | Blocks |
|---|---|---|---|---|
| C.1 | [01-config-and-dependencies.md](./01-config-and-dependencies.md) | Settings (`docker_model_runner_url`, `llm_model`) + `httpx` dependency | Any dev | C.2, C.4 |
| C.2 | [02-llm-service.md](./02-llm-service.md) | New `app/services/llm_service.py` — SSE streaming client for Qwen | Backend dev | C.4 |
| C.3 | [03-websocket-router.md](./03-websocket-router.md) | New `app/routers/guidance.py` + `main.py` registration | Backend dev | C.4 |
| C.4 | [04-pipeline-wiring.md](./04-pipeline-wiring.md) | Wire `stream_guidance` + `broadcast_token` into `command_pipeline_service` | Backend dev | C.5 |
| C.5 | [05-verification-acceptance.md](./05-verification-acceptance.md) | End-to-end smoke test + acceptance checklist | Whoever finishes last | — |

## Dependency graph

```
C.1 ──┬──► C.2 ──┐
      │          ├──► C.4 ──► C.5
      └──► C.3 ──┘
```

C.1 is the unblocker. C.2 and C.3 are independent and can run in parallel once C.1 lands. C.4 stitches them into the command pipeline. C.5 is the acceptance gate.

## Out of scope for Phase C

- Tauri overlay code that consumes the WebSocket — deferred to Phase F.
- Prompt-engineering tuning beyond the spec defaults (temperature 0.3, 256 max tokens).
- Multi-session fan-out — single-user desktop assumption holds; one WebSocket per `session_id`.
- Authentication on the WebSocket — local-only, no auth in Phase C.
- Re-attempting failed LLM calls — a downed Model Runner is treated as "no guidance this turn" and the pipeline silently continues.

## Definition of done for the whole phase

All acceptance items in [05-verification-acceptance.md](./05-verification-acceptance.md) are checked, `pytest tests/` is green (all existing + new tests, target ~33 passing), and `POST /api/command` produces coherent AutoCAD guidance on the connected WebSocket within 2–5 seconds.
