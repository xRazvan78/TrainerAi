# AI Copilot — Agent Orchestra

This document describes every agent and subagent in the `.github/agents/` folder, what each one does, what it owns, and how they connect. The system is built in three tiers: one commander, four core agents, and eleven subagents.

---

## How the pipeline works

Every 200–500ms, Tauri captures a screenshot of the user's AutoCAD session and sends it over WebSocket to the FastAPI backend. From there, the following sequence runs automatically:

```
Screen capture
      ↓
Frame diff filter        ← skip if nothing changed
      ↓
YOLOv8 + EasyOCR        ← run in parallel
      ↓
Session state update
      ↓
RAG retrieval + Error detection    ← run in parallel
      ↓
Prompt build → Qwen 3.5 inference → Validate
      ↓
Stream guidance to Tauri overlay
      ↓
Outcome tracking + Data logging + Skill calibration    ← async, non-blocking
```

---

## Tier 1 — Commander

### `Conductor.agent.md`

The master orchestrator. Every development task in this project goes through the Conductor first. It manages the full **Planning → Implementation → Review → Commit** cycle by delegating to specialised subagents — it never writes code itself.

**Owns**: task routing, plan files, phase tracking, commit message generation, mandatory approval gates between phases.

**Does not own**: any implementation detail of the copilot runtime itself.

**Key behaviour**: stops and waits for user approval after presenting a plan, after each phase completes, and after the final completion report. It never auto-proceeds past these checkpoints.

---

## Tier 2 — Core Agents

Each core agent owns a specific domain of the runtime pipeline. They coordinate their own subagents and produce a single structured output consumed by the next agent in the chain.

---

### `perception-agent.agent.md`

Owns everything visual. Receives raw JPEG frames from Tauri, runs change detection, detects UI elements with YOLOv8, reads text with EasyOCR, and assembles a `ScreenState` JSON for the Context Agent.

**Input**: JPEG frame + session_id over WebSocket  
**Output**: `ScreenState` JSON  
**Subagents**: `frame-diff-subagent`, `yolov8-subagent`, `easyocr-subagent`

**Key behaviour**: frame diff runs first — if the screen hasn't changed enough (< 15% pixel difference), YOLOv8 and EasyOCR are skipped entirely. When processing does run, YOLOv8 and EasyOCR execute in parallel via `asyncio.gather`.

---

### `context-agent.agent.md`

Owns memory and awareness. Takes the `ScreenState` from the Perception Agent, updates the user's session log, retrieves relevant AutoCAD documentation from pgvector, detects error patterns, and assembles a `ContextPacket` for the Guidance Agent.

**Input**: `ScreenState` JSON  
**Output**: `ContextPacket` JSON including `guidance_priority`  
**Subagents**: `session-state-subagent`, `rag-retrieval-subagent`, `error-detect-subagent`

**Key behaviour**: session state updates first (sequential), then RAG retrieval and error detection run in parallel. The `guidance_priority` field it sets (`error_correction`, `command_help`, `proactive_tip`, `idle`) directly controls what the Guidance Agent generates next.

---

### `guidance-agent.agent.md`

Owns the LLM. Takes the `ContextPacket`, selects the correct prompt template, calls the locally running Qwen 3.5 model, and streams tokens back to the Tauri overlay in real time. After streaming completes, validates the response before finalising it.

**Input**: `ContextPacket` JSON  
**Output**: streamed `guidance_chunk` WebSocket events + final `guidance_complete` event  
**Subagents**: `prompt-builder-subagent`, `qwen-inference-subagent`, `step-validator-subagent`

**Key behaviour**: if `guidance_priority` is `idle`, the entire agent short-circuits and no LLM call is made. Tokens are forwarded to the Tauri client immediately as they arrive — nothing is buffered. The `guidance_complete` event triggers the Feedback Agent.

---

### `feedback-agent.agent.md`

Owns the learning loop. Runs fully asynchronously — it never blocks the main pipeline. After guidance is delivered, it observes the user's next actions to determine whether they followed the suggestion, logs confirmed successes to pgvector as training data, and adjusts the user's skill score and guidance verbosity for future sessions.

**Input**: `guidance_complete` event + next `ScreenState`  
**Output**: `FeedbackSignal` JSON to the Conductor  
**Subagents**: `outcome-tracker-subagent`, `data-logger-subagent`, `difficulty-calibrator-subagent`

**Key behaviour**: always invoked via `asyncio.create_task` — it runs in the background while the next frame is already being processed. Waits up to 8 seconds for the user's next action before classifying the outcome.

---

## Tier 3 — Subagents

Each subagent does exactly one thing. They implement code directly and do not orchestrate further.

---

### Perception subagents

#### `frame-diff-subagent.agent.md`

Compares the current JPEG frame against the last processed frame using MD5 hash and pixel difference. Returns whether the frame should be processed and the new frame hash.

**Always runs first** in the Perception pipeline. If it returns `should_process: false`, nothing else runs for this frame.

| Field | Value |
|---|---|
| Diff threshold | 15% pixel change (configurable) |
| Comparison resolution | 320×180 px grayscale |
| Per-pixel noise filter | 10 grey levels (ignores JPEG artefacts) |
| Performance target | < 5ms total |
| Fail behaviour | Corrupted JPEG → skip frame. Numpy error → process frame (fail open) |

---

#### `yolov8-subagent.agent.md`

Runs YOLOv8 inference on the full JPEG frame and returns a list of bounding boxes with class labels and confidence scores for all detected AutoCAD UI elements.

**Runs in parallel** with `easyocr-subagent` after the diff filter passes.

| Detected classes | `toolbar`, `button`, `menu`, `dialog`, `canvas`, `input_field`, `panel` |
|---|---|
| Confidence threshold | 0.5 (configurable) |
| Model file | `backend/models/autocad_yolov8/best.pt` |
| Recommended base | `yolov8n.pt` (nano) for CPU, `yolov8s.pt` (small) for GPU |
| Performance target | < 50ms (GPU), < 210ms (CPU) |
| Fail behaviour | CUDA OOM → fall back to CPU for this frame |

---

#### `easyocr-subagent.agent.md`

Crops each bounding box region from the frame, applies class-specific pre-processing (contrast enhancement for buttons/panels, upscaling for small regions), and runs EasyOCR to extract text from each crop.

**Runs in parallel** with `yolov8-subagent`. Always returns one text entry per input region — never drops a region even if no text is found.

| Language | English (default). Configurable at startup for other locales |
|---|---|
| Crop padding | 4px per edge (avoids clipping edge characters) |
| Min text size | 8px (ignores noise) |
| Performance target | < 80ms for 10 regions (GPU), < 200ms (CPU) |
| Fail behaviour | Individual crop failure → null text for that region, pipeline continues |

---

### Context subagents

#### `session-state-subagent.agent.md`

Maintains the per-session action log in memory. Receives each ScreenState and returns an enriched session object including the active tool, previous tool, command sequence, action count, session duration, and current context label.

**Always runs first** in the Context pipeline before RAG and error detection.

| Context labels | `idle`, `command_active`, `drawing_mode`, `dialog_open` |
|---|---|
| Command sequence | Last 10 tools used, no consecutive duplicates |
| Storage | In-memory dict (ephemeral) + PostgreSQL checkpoint every 60s |
| Performance target | < 5ms (pure in-memory, zero I/O) |

---

#### `rag-retrieval-subagent.agent.md`

Encodes the current session context (active tool, context label, command sequence, error type) into a query vector using `all-MiniLM-L6-v2` (384-dim) and runs a cosine similarity search against pgvector to retrieve the most relevant AutoCAD documentation chunks.

**Runs in parallel** with `error-detect-subagent`.

| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
|---|---|
| pgvector index | `ivfflat` with `vector_cosine_ops`, `lists=100` |
| Similarity threshold | 0.72 (configurable) |
| Token budget | 1200 tokens max across all returned docs |
| Document sources | `autocad_command_reference`, `autocad_workflow_guide`, `autocad_error_guide`, `user_confirmed` |
| Performance target | < 35ms (GPU), < 70ms (CPU) |
| Fail behaviour | DB connection failure → empty result, pipeline continues |

---

#### `error-detect-subagent.agent.md`

Analyses the session state and screen elements against six deterministic rules to detect AutoCAD error patterns. Returns a structured error signal with type, severity, description, and suggested correction.

**Runs in parallel** with `rag-retrieval-subagent`. First matching rule wins — no further rules are evaluated after a match.

| Rule | Error type | Severity |
|---|---|---|
| RULE_01 | `wrong_command_order` — new command started while another is active | critical |
| RULE_02 | `repeated_undo` — UNDO used 3+ times consecutively | warning |
| RULE_03 | `dialog_ignored` — dialog open > 20 frames without interaction | warning |
| RULE_04 | `repeated_command` — same non-navigation command repeated 4+ times | warning |
| RULE_05 | `invalid_input` — input field active but no tool detected | warning |
| RULE_06 | `stuck_on_command` — same command active > 60 frames continuously | warning |

**Performance target**: < 5ms (pure in-memory rule matching, zero I/O)

---

### Guidance subagents

#### `prompt-builder-subagent.agent.md`

Selects the correct prompt template based on `guidance_priority`, injects session context, RAG docs, and error signals, enforces the 1800-token budget, and returns a fully assembled system prompt and user message ready for Qwen 3.5.

| Templates | `error_correction`, `command_help`, `proactive_tip` |
|---|---|
| Token budget | 1800 total: 300 system + 300 context + 1200 RAG (RAG truncated first) |
| Verbosity levels | `detailed` (beginner) · `standard` (intermediate) · `concise` (expert) |
| Guidance depth | `full_tutorial` (5 steps) · `steps_with_explanation` (4) · `steps_only` (3) |
| Performance target | < 10ms (pure string operations) |
| Idle behaviour | Returns null prompts immediately — no computation |

---

#### `qwen-inference-subagent.agent.md`

Sends the assembled prompt to the locally running Qwen 3.5 endpoint (Ollama API format) and streams every token chunk immediately to the Tauri overlay via WebSocket. Never buffers — each chunk is forwarded as it arrives.

| Endpoint | `http://localhost:11434/api/chat` (Ollama) |
|---|---|
| Model | `qwen2.5:7b` |
| Temperature | 0.3 (low randomness for precise technical instructions) |
| Max new tokens | 300 |
| First token target | < 500ms (GPU), < 1500ms (CPU-only) |
| Full response target | < 2000ms |
| Fail behaviour | Endpoint unreachable → error result returned, pipeline does not crash |

---

#### `step-validator-subagent.agent.md`

Validates the full LLM response against six deterministic checks after streaming completes. If any check fails, replaces the response with a safe priority-specific fallback message.

All checks always run — unlike error detection, the first failure does not stop evaluation. All issues are collected for debugging.

| Check | What it catches |
|---|---|
| VCHECK_01 | Null or empty response |
| VCHECK_02 | Response < 8 words or > 350 words |
| VCHECK_03 | Hallucinated AutoCAD command names (ALL_CAPS words not in known command list) |
| VCHECK_04 | Response doesn't mention the active tool or error type |
| VCHECK_05 | Destructive instructions (delete file, uninstall, format drive, etc.) |
| VCHECK_06 | Truncated mid-sentence response (finish_reason is `length`, no closing punctuation) |

**Performance target**: < 10ms (pure string and regex operations)

---

### Feedback subagents

#### `outcome-tracker-subagent.agent.md`

Compares the session state before and after guidance was delivered and classifies the user's response into one of four outcomes. Uses a different comparison method depending on the guidance type.

**Always runs first** in the Feedback pipeline before logging and calibration.

| Outcome | Meaning |
|---|---|
| `followed` | User took the suggested action and the error/trigger is resolved |
| `partially_followed` | User moved toward the correction but didn't complete it (e.g. pressed ESC but didn't reissue the command) |
| `ignored` | No relevant action taken within the observation window |
| `unclear` | Timed out, too few frames, or ambiguous screen change |

| Observation window | 8 seconds (4–8 frames at 2–5fps) |
|---|---|
| Performance target | < 10ms (pure dict comparison) |
| Fail behaviour | Method exception → returns `unclear` gracefully |

---

#### `data-logger-subagent.agent.md`

Writes confirmed successful guidance examples to the `training_examples` PostgreSQL table and a corresponding embedding to the `embeddings` pgvector table. Only logs when the outcome meets the quality threshold.

| Log condition | `followed` or `partially_followed` AND confidence ≥ 0.80 |
|---|---|
| Never logs | `ignored`, `unclear`, or confidence < 0.80 |
| Embedding model | `all-MiniLM-L6-v2` (same as RAG retrieval) |
| Source tag | `user_confirmed` (distinguishes learned examples from pre-loaded docs) |
| Write order | `training_examples` first, then `embeddings` (separate, not transactional) |
| Duplicate handling | `ON CONFLICT (doc_id) DO NOTHING` — both inserts are idempotent |
| Performance target | < 35ms (GPU), < 70ms (CPU) |

---

#### `difficulty-calibrator-subagent.agent.md`

Updates the user's skill score based on the latest outcome using a confidence-weighted delta formula, applies early-session stabilisation and streak/struggle modifiers, and returns the new verbosity and guidance depth settings for future prompts.

**Runs in parallel** with `data-logger-subagent`. Returns values only — the Feedback Agent writes them to the session store and PostgreSQL.

| Initial skill score | 0.40 (intermediate-beginner) |
|---|---|
| `followed` delta | +0.08 × confidence |
| `partially_followed` delta | +0.03 × confidence |
| `ignored` delta | −0.05 × confidence |
| `unclear` delta | 0.00 |
| Streak bonus | +0.05 if last 5 outcomes all `followed` |
| Struggle penalty | −0.05 if last 4 outcomes all `ignored` |
| Early stabilisation | First 10 outcomes: delta × 0.5 |
| Score range | Clamped to [0.0, 1.0] |
| Hysteresis band | 0.03 — prevents oscillation near threshold boundaries |

| Score range | Verbosity | Guidance depth |
|---|---|---|
| 0.00 – 0.35 | `detailed` | `full_tutorial` (5 steps, explain why) |
| 0.36 – 0.65 | `standard` | `steps_with_explanation` (4 steps, brief reason) |
| 0.66 – 1.00 | `concise` | `steps_only` (3 steps, actions only) |

---

## Shared services

All agents share these infrastructure components. Schema changes must go through the Conductor's plan cycle — no agent modifies schemas directly.

| Service | Purpose |
|---|---|
| **WebSocket event bus** | Async inter-agent messaging, frame delivery, token streaming |
| **PostgreSQL** | Sessions, training examples, persistent state |
| **pgvector (`embeddings` table)** | 384-dim vectors for RAG retrieval, `ivfflat` index |
| **In-memory session store** | Python dict keyed by `session_id`, ephemeral per process restart |
| **`all-MiniLM-L6-v2`** | Shared embedding model — loaded once at startup, injected into RAG retrieval and data logger |

---

## Agent file locations

All agent files live in `.github/agents/`. VS Code Copilot detects them automatically.

```
.github/agents/
├── Conductor.agent.md
├── perception-agent.agent.md
├── context-agent.agent.md
├── guidance-agent.agent.md
├── feedback-agent.agent.md
├── frame-diff-subagent.agent.md
├── yolov8-subagent.agent.md
├── easyocr-subagent.agent.md
├── session-state-subagent.agent.md
├── rag-retrieval-subagent.agent.md
├── error-detect-subagent.agent.md
├── prompt-builder-subagent.agent.md
├── qwen-inference-subagent.agent.md
├── step-validator-subagent.agent.md
├── outcome-tracker-subagent.agent.md
├── data-logger-subagent.agent.md
└── difficulty-calibrator-subagent.agent.md
```

> **Model**: all agents use `Claude Haiku 4.5 (copilot)`. Make sure this model is enabled in your GitHub Copilot settings before using any agent.

---

## Quick reference — who owns what

| Concern | Agent |
|---|---|
| Screen capture and change detection | `frame-diff-subagent` |
| AutoCAD UI element detection | `yolov8-subagent` |
| Text extraction from screen regions | `easyocr-subagent` |
| User action history and active tool | `session-state-subagent` |
| Documentation retrieval from pgvector | `rag-retrieval-subagent` |
| Mistake detection and error signals | `error-detect-subagent` |
| LLM prompt assembly | `prompt-builder-subagent` |
| Qwen 3.5 inference and token streaming | `qwen-inference-subagent` |
| Response quality validation | `step-validator-subagent` |
| Did the user follow the guidance? | `outcome-tracker-subagent` |
| Writing training examples to pgvector | `data-logger-subagent` |
| User skill score and verbosity settings | `difficulty-calibrator-subagent` |
| Development lifecycle orchestration | `Conductor` |