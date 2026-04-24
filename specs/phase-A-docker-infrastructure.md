# Phase A — Docker Infrastructure

**Prerequisite for**: Every other phase  
**Estimated effort**: 1–2 hours  
**Outside VS Code work**: Yes — Docker Desktop, terminal commands

---

## Goal

Spin up a reproducible local environment with:

- PostgreSQL 18 + pgvector extension (vector database)
- Docker Desktop Model Runner serving `qwen3.5:35B-A3B-Q4_K_M` (already downloaded via Docker Desktop Models tab)

No other phase can be tested end-to-end without this running.

---

## Outside VS Code — Step by Step

### 1. Verify Docker Desktop is running

Open PowerShell and confirm:

```powershell
docker version
docker compose version
```

Both must return version info without errors.

---

### 2. Verify the model is available in Docker Desktop

The model was downloaded via Docker Desktop's **Models** tab. Confirm it is listed:

```powershell
docker model ls
```

You should see `ai/qwen3.5:35B-A3B-Q4_K_M` in the output. If it appears under a slightly different tag, note the exact name — you will need it in the `.env` file.

---

### 3. Verify the pgvector image is available

```powershell
docker pull pgvector/pgvector:pg18
```

> If the `pg18` tag is not yet published on Docker Hub, check https://hub.docker.com/r/pgvector/pgvector/tags for the latest available PostgreSQL 18 image and use that exact tag in `docker-compose.yml`.

---

## In VS Code — Files to Create

### `docker-compose.yml` (project root)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18
    container_name: trainerai_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-trainerai}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-trainerai_pass}
      POSTGRES_DB: ${POSTGRES_DB:-trainerai_db}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-trainerai}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
```

> The Qwen model is managed by Docker Desktop Model Runner and does not need a Compose service entry.

---

### `.env.example` (project root)

```dotenv
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=trainerai
POSTGRES_PASSWORD=trainerai_pass
POSTGRES_DB=trainerai_db

# Docker Desktop Model Runner (LLM)
DOCKER_MODEL_RUNNER_URL=http://localhost:12434/engines/llama.cpp/v1
LLM_MODEL=ai/qwen3.5:35B-A3B-Q4_K_M

# Embedding model (used by sentence-transformers, not Ollama)
EMBED_MODEL_NAME=all-MiniLM-L6-v2
EMBED_DIM=384

# RAG settings
RAG_TOP_K=4
RAG_SIMILARITY_THRESHOLD=0.72
RAG_TOKEN_BUDGET=1200
```

Copy this to `.env` and fill in real values before starting the backend:

```powershell
Copy-Item .env.example .env
```

---

## Outside VS Code — Start the Stack

Once `docker-compose.yml` exists at the project root:

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi

# Start postgres in the background
docker compose up -d

# Watch logs to confirm postgres is healthy
docker compose logs -f
```

Wait for the postgres health check to pass (green `healthy` in `docker compose ps`).

---

## Outside VS Code — Bootstrap the Database Schema

The FastAPI app bootstraps the schema on startup (via `schema.py`). But you can also run it manually:

```powershell
# Enter the project backend folder
cd trainerAI_backend

# Create and activate a virtualenv (first time only)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy env file
Copy-Item ..\.env.example ..\.env   # edit values first

# Start the backend (this triggers schema bootstrap)
uvicorn app.main:app --reload
```

After startup, open http://localhost:8000/health — it should return `{"status":"ok"}`.

Then check http://localhost:8000/db/health — it should return `{"status":"ok","pool":"connected"}`.

---

## Outside VS Code — Verify Docker Model Runner is Accessible

```powershell
# List downloaded models
docker model ls

# Quick non-streaming inference test (OpenAI-compatible API)
$body = @{
    model = "ai/qwen3.5:35B-A3B-Q4_K_M"
    messages = @(@{ role = "user"; content = "What is AutoCAD used for?" })
    stream = $false
    max_tokens = 100
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
    -Uri http://localhost:12434/engines/llama.cpp/v1/chat/completions `
    -Body $body `
    -ContentType "application/json"
```

The response will have a `choices[0].message.content` field with generated text. This confirms the model is loaded and the OpenAI-compatible API is responding.

---

## Acceptance Criteria

- [ ] `docker compose ps` shows `trainerai_postgres` as `healthy`
- [ ] `docker model ls` lists `ai/qwen3.5:35B-A3B-Q4_K_M`
- [ ] `GET http://localhost:8000/db/health` returns `200 OK`
- [ ] Docker Model Runner test prompt returns a coherent response
- [ ] `.env` file exists at project root with correct values

---

## Common Issues

| Symptom                                               | Fix                                                                        |
| ----------------------------------------------------- | -------------------------------------------------------------------------- |
| `pg_isready` fails in healthcheck                     | Wait 30s; postgres takes time to initialise on first run                   |
| Port 5432 already in use                              | Stop any local PostgreSQL service: `Stop-Service postgresql*`              |
| `docker model ls` shows no models                     | Re-open Docker Desktop → Models tab → confirm the model is downloaded      |
| Model Runner returns connection refused on port 12434 | Ensure Docker Desktop is running and is version 4.40 or newer              |
| Model name not found in API response                  | Check `docker model ls` for the exact tag and update `LLM_MODEL` in `.env` |
