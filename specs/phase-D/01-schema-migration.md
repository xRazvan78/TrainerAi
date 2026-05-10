# D.1 — Schema + CRUD changes

**Depends on:** nothing (can start immediately)
**Blocks:** D.3, D.5
**Estimated effort:** 1–2 h

## Goal

Make `embeddings` rows carry per-chunk metadata (source video, timestamps, AutoCAD tool hint, tags) and make `create_embedding` idempotent so re-running ingestion on the same video does not duplicate rows. Also add a batched embedder helper so D.3 can encode hundreds of chunks in one shot.

## Why metadata matters

The chunker (D.3) produces useful structured info: `source_video`, `timestamp_start`, `timestamp_end`, `active_tool_hint`, `tags`. Without a column to hold it we lose:

- Citations in the overlay ("from minute 4:12 of fillet_basics.mp4").
- The ability to filter RAG retrieval by `active_tool` later (Phase G).
- The ability to delete or re-embed all rows belonging to one video.

## Changes

### 1. `trainerAI_backend/app/db/schema.py`

Update the `embeddings` `CREATE TABLE` and append an idempotent `ALTER TABLE` for existing dev DBs (mirror the pattern already used for `training_examples.context_retrieved` at `schema.py:56-60`).

```python
# Replace the embeddings CREATE TABLE statement with:
f"""
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    doc_id TEXT UNIQUE,
    source TEXT,
    content TEXT,
    embedding vector({VECTOR_DIMENSION}),
    metadata JSONB DEFAULT '{{}}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
```

Then append, after the existing embeddings index statement:

```python
"""
ALTER TABLE embeddings
-- Backward-compatible migration for databases created before Phase D.
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
""",
```

Note the doubled `{{}}` in the f-string above — `'{}'::jsonb` literal must survive f-string formatting.

`bootstrap_schema` is invoked from the FastAPI lifespan in `app/main.py`, so a backend restart applies the migration.

### 2. `trainerAI_backend/app/db/crud.py`

Update `create_embedding` (line 167) to accept `metadata` and to upsert on `doc_id` conflict. Update SELECTs in `get_embedding`, `list_embeddings`, `update_embedding`, and `query_similar_embeddings` to return `metadata`.

```python
async def create_embedding(
    pool: asyncpg.Pool,
    doc_id: str,
    source: str,
    content: str,
    embedding: Sequence[float],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    vector_literal = to_vector_literal(embedding)
    metadata_json = json.dumps(metadata or {})

    async with pool.acquire() as connection:
        record = await connection.fetchrow(
            """
            INSERT INTO embeddings (doc_id, source, content, embedding, metadata)
            VALUES ($1, $2, $3, $4::vector, $5::jsonb)
            ON CONFLICT (doc_id) DO UPDATE
              SET source = EXCLUDED.source,
                  content = EXCLUDED.content,
                  embedding = EXCLUDED.embedding,
                  metadata = EXCLUDED.metadata
            RETURNING doc_id, source, content, embedding::text AS embedding_text,
                      metadata, created_at;
            """,
            doc_id,
            source,
            content,
            vector_literal,
            metadata_json,
        )
    return _embedding_record_to_dict(record)
```

`_embedding_record_to_dict` already passes through unknown columns via `dict(record)`, so `metadata` flows through automatically — but verify with a print/log on the first run.

For the SELECT helpers, simply add `, metadata` to the column list. Example for `get_embedding`:

```sql
SELECT doc_id, source, content, embedding::text AS embedding_text, metadata, created_at
FROM embeddings WHERE doc_id = $1;
```

`query_similar_embeddings` (line 253) should also return `metadata` so the RAG service and the eval harness (D.5) can render which video a hit came from:

```sql
SELECT doc_id, source, content, metadata,
       1 - (embedding <=> $1::vector) AS similarity_score
FROM embeddings
WHERE 1 - (embedding <=> $1::vector) >= $2
ORDER BY similarity_score DESC
LIMIT $3;
```

### 3. `trainerAI_backend/app/services/embedder_service.py`

Add a batched helper. Keeps the `lru_cache`-loaded model shared with `embed_text`.

```python
def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Embed many strings in one model call. ~10x faster than calling embed_text
    in a loop for typical chunk counts. Returns a list of 384-dim vectors,
    one per input text, in the same order.
    """
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    assert vectors.shape[1] == _EXPECTED_DIM, (
        f"Embedding dimension mismatch: expected {_EXPECTED_DIM}, got {vectors.shape[1]}"
    )
    return vectors.tolist()
```

## Tests to update / add

- `tests/test_db_crud_helpers.py` — if existing tests call `create_embedding`, they continue to work (the new param has a default). Add one new test that round-trips `metadata`.
- `tests/test_embedder_service.py` — add a test that `embed_texts(["foo", "bar"])` returns two 384-dim vectors and that `embed_texts([])` returns `[]`.
- Add an upsert test: `create_embedding(...)` twice with the same `doc_id` — `SELECT COUNT(*) FROM embeddings WHERE doc_id = ...` returns 1; the second call's `content` wins.

## Acceptance

- [ ] `\d embeddings` shows the `metadata jsonb` column with default `'{}'`.
- [ ] `create_embedding(..., metadata={"foo": "bar"})` returns a row whose `metadata` round-trips.
- [ ] Calling `create_embedding` twice with the same `doc_id` does not raise and leaves a single row in the table.
- [ ] `embed_texts(["a", "b", "c"])` returns 3 vectors of length 384.
- [ ] `pytest tests/` green.
