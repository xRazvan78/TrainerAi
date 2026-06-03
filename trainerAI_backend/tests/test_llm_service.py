import asyncio

import httpx
import pytest

from app.services.llm_service import _build_user_prompt, stream_guidance


def test_stream_guidance_parses_sse_chunks(monkeypatch):
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: {"choices":[{"delta":{}}]}',
        '',
        'data: not-json',
        'data: [DONE]',
        'data: {"choices":[{"delta":{"content":"never"}}]}',
    ]

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())

    async def run():
        tokens = []
        async for token in stream_guidance("LINE", "LINE", ["doc"], ["LINE"]):
            tokens.append(token)
        return tokens

    result = asyncio.run(run())
    assert result == ["Hello", " world"]


def test_build_user_prompt_includes_history_and_context():
    prompt = _build_user_prompt(
        command_text="LINE 0,0 10,10",
        active_tool="LINE",
        context_docs=["Doc A", "Doc B"],
        command_sequence=["MOVE", "COPY", "LINE"],
    )
    assert "Active AutoCAD tool: LINE" in prompt
    assert "how to use the LINE tool" in prompt
    assert "MOVE, COPY, LINE" in prompt
    assert "Doc A\n---\nDoc B" in prompt

    prompt_empty = _build_user_prompt(
        command_text="LINE 0,0 10,10",
        active_tool="LINE",
        context_docs=[],
        command_sequence=[],
    )
    assert "No relevant docs found." in prompt_empty
    assert "Recent command history: none" in prompt_empty
