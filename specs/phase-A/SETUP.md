# Phase A — Setup Instructions

Follow every step in order. Each section says exactly where to run the commands.

---

## Prerequisites

- Docker Desktop installed and **running** (icon in system tray)
- Docker Desktop version **4.40 or newer** (required for Model Runner)
- Python 3.10+ installed and on PATH
- The Qwen model already downloaded via Docker Desktop → Models tab

---

## Step 1 — Confirm Docker is working

**Where:** PowerShell (any directory)

```powershell
docker version
docker compose version
```

Both commands must print version info with no errors. If either fails, Docker Desktop is not running or not installed correctly.

---

## Step 2 — Pull the PostgreSQL + pgvector image

**Where:** PowerShell (any directory)

```powershell
docker pull pgvector/pgvector:pg18
```

If the command errors with "manifest unknown", the `pg18` tag is not yet published.
In that case:

1. Open https://hub.docker.com/r/pgvector/pgvector/tags in a browser
2. Find the latest tag that includes `pg18` (e.g. `0.8.0-pg18`)
3. Open `docker-compose.yml` at the project root and replace `pgvector/pgvector:pg18` with that exact tag

---

## Step 3 — Confirm the Qwen model is available

**Where:** PowerShell (any directory)

```powershell
docker model ls
```

You should see a line containing `ai/qwen3.5:35B-A3B-Q4_K_M`.

If the model is listed under a slightly different tag, note the exact name — you will need it in the next step.

If the list is empty, open Docker Desktop → Models tab and wait for the download to finish.

---

## Step 4 — Create the `.env` file

**Where:** PowerShell, from the project root

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi
Copy-Item .env.example .env
```

Then open `.env` (in VS Code or any text editor) and verify the values:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=trainerai
POSTGRES_PASSWORD=trainerai_pass
POSTGRES_DB=trainerai_db

DOCKER_MODEL_RUNNER_URL=http://localhost:12434/engines/llama.cpp/v1
LLM_MODEL=ai/qwen3.5:35B-A3B-Q4_K_M

EMBED_MODEL_NAME=all-MiniLM-L6-v2
EMBED_DIM=384

RAG_TOP_K=4
RAG_SIMILARITY_THRESHOLD=0.72
RAG_TOKEN_BUDGET=1200
```

If the model tag from Step 3 is different, update `LLM_MODEL` to match.

---

## Step 5 — Start PostgreSQL

**Where:** PowerShell, from the project root

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi
docker compose up -d
```

Wait about 15–30 seconds, then check the container status:

```powershell
docker compose ps
```

The `trainerai_postgres` container must show `healthy` in the Status column.
If it shows `starting`, wait a bit longer and run `docker compose ps` again.

To watch live logs while it starts:

```powershell
docker compose logs -f
```

Press `Ctrl+C` to stop following logs (this does not stop the container).

### Troubleshooting port conflicts

If you see an error like `port 5432 is already allocated`, a local PostgreSQL service is running.
Stop it first:

```powershell
Stop-Service postgresql*
```

Then retry `docker compose up -d`.

---

## Step 6 — Set up the Python virtual environment

**Where:** PowerShell, from the `trainerAI_backend` folder

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

You should see `(.venv)` at the start of your prompt after activation.

If `Activate.ps1` is blocked by execution policy, run this first (once):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Step 7 — Start the FastAPI backend

**Where:** PowerShell, from the `trainerAI_backend` folder, with `.venv` activated

```powershell
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi\trainerAI_backend
.venv\Scripts\Activate.ps1   # skip if already activated
uvicorn app.main:app --reload
```

The first startup will bootstrap the database schema automatically.
You should see output ending with:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Leave this terminal open — the backend must stay running for all tests below.

---

## Step 8 — Verify everything is working

Open a **second** PowerShell window for these checks (keep the backend running in the first).

### 8a. Backend health

**Where:** Browser or PowerShell

Open in browser: `http://localhost:8000/health`

Expected response: `{"status":"ok"}`

Or via PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### 8b. Database connection

Open in browser: `http://localhost:8000/db/health`

Expected response: `{"status":"ok","pool":"connected"}`

Or via PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/db/health
```

### 8c. Qwen model responds

**Where:** PowerShell (any directory)

```powershell
$body = @{
    model   = "ai/qwen3.5:35B-A3B-Q4_K_M"
    messages = @(@{ role = "user"; content = "What is AutoCAD used for?" })
    stream   = $false
    max_tokens = 100
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:12434/engines/llama.cpp/v1/chat/completions" `
    -Body $body `
    -ContentType "application/json"
```

Expected: the response object has a `choices` array; `choices[0].message.content` contains a sentence or two about AutoCAD.

If you get `Connection refused`, Docker Desktop is not running or is older than version 4.40.

---

## Acceptance Checklist

- [ ] `docker compose ps` → `trainerai_postgres` status is `healthy`
- [ ] `docker model ls` → `ai/qwen3.5:35B-A3B-Q4_K_M` is listed
- [ ] `http://localhost:8000/health` → `{"status":"ok"}`
- [ ] `http://localhost:8000/db/health` → `{"status":"ok","pool":"connected"}`
- [ ] Qwen test prompt returns coherent text about AutoCAD

All five checks passing means Phase A is complete.

---

## Stopping the stack

When you are done working, stop everything cleanly:

```powershell
# Stop the FastAPI backend
# Press Ctrl+C in the terminal where uvicorn is running

# Stop PostgreSQL (data is preserved in the Docker volume)
cd d:\faculta\An_3\Semestru_1\Inteligenta_Artificiala\Proiect\TrainerAi
docker compose down
```

To start again next time, repeat Steps 5 and 7 only (no need to redo Steps 1–4).
