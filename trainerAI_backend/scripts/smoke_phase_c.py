"""
Manual smoke test for Phase C end-to-end: POST /api/command -> WebSocket token stream.

Prerequisites:
  - docker compose up -d (pgvector)
  - Docker Desktop Model Runner serving ai/qwen3.5:35B-A3B-Q4_K_M
  - uvicorn app.main:app --reload (from trainerAI_backend/)
  - pip install websockets (client dep, not in requirements.txt)

Run from trainerAI_backend/:
  python scripts/smoke_phase_c.py
"""
import asyncio
import httpx
import websockets

SESSION_ID = "smoke-phase-c"
BASE = "http://localhost:8000"
WS = f"ws://localhost:8000/api/guidance/ws/{SESSION_ID}"


async def main():
    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE}/db/sessions", json={
            "session_id": SESSION_ID,
            "skill_score": 0.5,
            "verbosity_level": "medium",
        })

    async with websockets.connect(WS) as ws:
        async with httpx.AsyncClient() as client:
            await client.post(f"{BASE}/api/command", json={
                "text": "LINE",
                "timestamp": "2026-05-21T12:00:00Z",
                "session_id": SESSION_ID,
            })

        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=90)
                print(msg, end="", flush=True)
                if '"type":"done"' in msg:
                    break
        except asyncio.TimeoutError:
            print("\n[TIMEOUT] no done marker within 90 s")


asyncio.run(main())
