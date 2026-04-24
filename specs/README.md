# TrainerAI — Implementation Roadmap

## What This Project Is

An always-on-top transparent overlay window that runs alongside AutoCAD. It watches the screen, recognises what the user is doing, retrieves relevant knowledge from a local vector database, and streams context-aware guidance text in real time using a locally-hosted Qwen LLM.

```
AutoCAD screen
      │
      ▼
[Tauri overlay: WGC screen capture]
      │ POST /api/perception/state  (base64 frame + bounding boxes)
      ▼
[FastAPI backend]
      │
      ├─► session_state_service  → updates session + active_tool
      ├─► rag_service            → semantic search in pgvector
      ├─► llm_service            → Docker Desktop Model Runner / Qwen 3.5 prompt + stream
      └─► feedback_logger        → writes training examples to DB
      │
      ▼ WebSocket stream
[Tauri overlay: Dioxus UI]
      │ renders guidance text token by token
      ▼
User sees inline tips
```

---

## Current State (as of start of roadmap)

| Area                         | Status      | Notes                                                      |
| ---------------------------- | ----------- | ---------------------------------------------------------- |
| PostgreSQL + pgvector schema | ✅ Complete | 4 tables, 384-dim ivfflat index                            |
| FastAPI CRUD + routers       | ✅ Complete | Sessions, embeddings, training_examples, perception_states |
| Command ingestion pipeline   | ✅ Complete | 202 ack, async background task                             |
| RAG retrieval service        | ✅ Complete | Structurally correct, **mock embedder**                    |
| Embedder service             | ⚠️ Mock     | SHA-256 hash, not semantic                                 |
| Qwen / LLM service           | ❌ Missing  | Hardcoded mock string returned                             |
| WebSocket streaming          | ❌ Missing  | —                                                          |
| Video training pipeline      | ❌ Missing  | pgvector tables are empty                                  |
| Tauri screen capture         | ❌ Stub     | WGC not implemented                                        |
| Tauri → backend connection   | ❌ Stub     | Hardcoded responses                                        |
| YOLOv8 / EasyOCR on backend  | ❌ Missing  | Perception endpoint accepts JSONB but no inference         |
| Docker setup                 | ❌ Missing  | No compose file                                            |

---

## Phase Execution Order

```
Phase A (Docker)
    │
    ├──► Phase B (Real Embeddings)
    │         │
    │         └──► Phase D (Video Training Pipeline)
    │
    └──► Phase C (Qwen LLM + WebSocket)
              │
              └──► Phase F (Full Pipeline Connection)
                        ▲
Phase E (Screen Capture) ┘

Phase G (AutoCAD-Specific Detection) — runs after F
```

Phases A and E can start in parallel from day one.
Phase D requires Phase B to be done first.
Phase F requires C and E to both be done.

---

## Phase Summary

| Phase                                      | Title                      | Unlocks                                   |
| ------------------------------------------ | -------------------------- | ----------------------------------------- |
| [A](./phase-A-docker-infrastructure.md)    | Docker Infrastructure      | Everything that needs a running DB or LLM |
| [B](./phase-B-real-embeddings.md)          | Real Semantic Embeddings   | Meaningful RAG results                    |
| [C](./phase-C-qwen-llm-integration.md)     | Qwen 3.5 LLM + WebSocket   | Actual AI guidance text + streaming       |
| [D](./phase-D-video-training-pipeline.md)  | Video Training Pipeline    | Knowledge base populated                  |
| [E](./phase-E-screen-capture.md)           | Screen Capture (Tauri/WGC) | Real-time perception input                |
| [F](./phase-F-full-pipeline-connection.md) | Full Pipeline Connection   | End-to-end working system                 |
| [G](./phase-G-autocad-detection.md)        | AutoCAD-Specific Detection | Production quality                        |

---

## Technology Stack

| Component           | Technology                                             | Notes                                                 |
| ------------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| Backend API         | FastAPI + asyncpg                                      | Already implemented                                   |
| Vector DB           | PostgreSQL 18 + pgvector                               | 384-dim embeddings                                    |
| Embeddings          | sentence-transformers all-MiniLM-L6-v2                 | 384-dim, free, local                                  |
| LLM                 | qwen3.5:35B-A3B-Q4_K_M via Docker Desktop Model Runner | MoE — only 3.5B active params at inference            |
| Screen capture      | Windows.Graphics.Capture (WGC) via `windows` crate     | Requires Windows 10+                                  |
| UI framework        | Dioxus 0.7 (Rust/WASM) + Tauri 2                       | Transparent overlay                                   |
| Object detection    | YOLOv8 (ultralytics)                                   | AutoCAD UI element detection                          |
| OCR                 | EasyOCR                                                | Text extraction from screen regions                   |
| Video transcription | OpenAI Whisper (local)                                 | Tutorial audio → text                                 |
| Containerisation    | Docker Compose                                         | PostgreSQL only (LLM via Docker Desktop Model Runner) |

---

## Repository Layout (Target)

```
TrainerAi/
├── docker-compose.yml          ← Phase A
├── .env.example                ← Phase A
├── specs/                      ← this folder
├── trainerAI_backend/
│   ├── requirements.txt        ← Phase B update
│   └── app/
│       ├── services/
│       │   ├── embedder_service.py     ← Phase B rewrite
│       │   ├── llm_service.py          ← Phase C new
│       │   └── command_pipeline_service.py  ← Phase C update
│       ├── routers/
│       │   └── guidance.py             ← Phase C new (WebSocket)
│       └── training/                   ← Phase D new module
│           ├── __init__.py
│           ├── video_extractor.py
│           ├── transcriber.py
│           ├── chunker.py
│           └── ingest.py
└── trainerAI_overlay/
    ├── src-tauri/src/
    │   ├── commands.rs         ← Phase E rewrite
    │   └── ws_client.rs        ← Phase F new
    └── src/main.rs             ← Phase F update (streaming UI)
```

---

## Hardware Requirements

| Resource | Minimum                      | Recommended                     |
| -------- | ---------------------------- | ------------------------------- |
| RAM      | 16 GB                        | 32 GB                           |
| GPU VRAM | 6 GB (Qwen MoE is efficient) | 8 GB+                           |
| Disk     | 20 GB free                   | 40 GB (for video training data) |
| OS       | Windows 10 2004+             | Windows 11 (better WGC support) |

The qwen3.5:35B-A3B-Q4_K_M model is a Mixture-of-Experts architecture with 35B total parameters but only ~3.5B active at any inference step. Q4_K_M quantisation brings the model weight size to roughly 20 GB on disk, and memory usage during inference to approximately 6–8 GB VRAM.
