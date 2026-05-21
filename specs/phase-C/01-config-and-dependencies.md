# Sub-phase C.1 — Config + Dependencies

## Overview

Add the two LLM-specific settings (`docker_model_runner_url`, `llm_model`) to the pydantic-settings model so the rest of Phase C can read them via `get_settings()`. Add `httpx` to `requirements.txt` since the LLM client needs an async HTTP/SSE-capable library. This is the unblocker for C.2 and C.4.

## Prerequisites

- Phase A (Docker stack) and Phase D (populated `embeddings` table) are complete.
- Docker Desktop Model Runner is installed and serving `ai/qwen3.5:35B-A3B-Q4_K_M` at `http://localhost:12434/engines/llama.cpp/v1` (verified manually — see §Testing).

## Goals

- `get_settings().docker_model_runner_url` and `.llm_model` are available, env-overridable, and have safe defaults.
- `httpx>=0.27.0` is installed and importable.
- `.env.example` documents the two new variables as optional overrides.

## Technical Design

### Settings additions (`app/config.py`)

The existing `Settings` class uses `Field(default=..., validation_alias="ENV_NAME")` for each field. Mirror that pattern:

```python
docker_model_runner_url: str = Field(
    default="http://localhost:12434/engines/llama.cpp/v1",
    validation_alias="DOCKER_MODEL_RUNNER_URL",
)
llm_model: str = Field(
    default="ai/qwen3.5:35B-A3B-Q4_K_M",
    validation_alias="LLM_MODEL",
)
```

These fields are read-only at runtime (no model_validator post-processing needed).

### Dependency

`requirements.txt` adds a single line: `httpx>=0.27.0`. No version pin upper-bound — httpx 0.27 is the first release with stable async streaming API contracts used here.

### `.env.example`

Append two commented-out lines (so they don't override the default unless deliberately uncommented):

```
# DOCKER_MODEL_RUNNER_URL=http://localhost:12434/engines/llama.cpp/v1
# LLM_MODEL=ai/qwen3.5:35B-A3B-Q4_K_M
```

## Implementation Steps

1. Open `trainerAI_backend/app/config.py`. After the existing `postgres_*` fields and before `model_config`, add the two `Field(...)` declarations shown above.
2. Open `trainerAI_backend/requirements.txt`. Append `httpx>=0.27.0` on a new line.
3. Open `.env.example` at the repo root. Append the two commented variables shown above.
4. Run `pip install -r trainerAI_backend/requirements.txt` from a fresh terminal — confirm `httpx` installs cleanly.
5. Open `trainerAI_backend/tests/test_config.py` and read the existing tests to understand the fixture pattern. Add one new test asserting that `get_settings().docker_model_runner_url` and `.llm_model` return the defaults when the env vars are unset (use `monkeypatch.delenv(..., raising=False)` to scrub any inherited value, then clear the `lru_cache` via `get_settings.cache_clear()` before reading).

## File & Directory Changes

| Path | Change |
|---|---|
| `trainerAI_backend/app/config.py` | Add two `Field` declarations on `Settings`. |
| `trainerAI_backend/requirements.txt` | Append `httpx>=0.27.0`. |
| `.env.example` | Append two commented env vars. |
| `trainerAI_backend/tests/test_config.py` | Add one test for the new defaults. |

## Testing & Validation

- `pytest tests/test_config.py -v` — all existing tests still pass plus the new default-values test.
- `python -c "import httpx; print(httpx.__version__)"` — prints 0.27.0 or higher.
- `python -c "from app.config import get_settings; s = get_settings(); print(s.docker_model_runner_url, s.llm_model)"` from `trainerAI_backend/` prints the expected defaults.

Manual sanity check that the Model Runner is actually reachable (do this once now to fail fast before C.2):

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:12434/engines/llama.cpp/v1/chat/completions `
  -Body (@{ model = "ai/qwen3.5:35B-A3B-Q4_K_M"; messages = @(@{role="user";content="say hi"}); stream=$false; max_tokens=20 } | ConvertTo-Json -Depth 5) `
  -ContentType "application/json"
```

Expected: a JSON response with `choices[0].message.content` containing a short greeting.

## Edge Cases & Risks

- **Pydantic-settings field ordering**: declarative — order doesn't matter. No risk.
- **`lru_cache` staleness in tests**: any test that overrides env vars must call `get_settings.cache_clear()` before re-reading, or use a fresh `Settings()` instance directly. The existing `test_config.py` already handles this pattern.
- **Model Runner not running**: this sub-phase doesn't depend on it at runtime, but flag it now — C.5's verification will fail otherwise.

## Notes

- Do **not** introduce a `from app.config import settings` module-level singleton import. The existing convention (used by `embedder_service.py` and `rag_service.py`) is to call `get_settings()` inside functions; preserve it for consistency and to keep `lru_cache` invalidation reliable in tests.
