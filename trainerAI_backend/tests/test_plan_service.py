"""
Tests for plan_service — unit tests covering advance, manual advance,
has_active_plan/clear, and generate_plan with mocked LLM + RAG.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest

from app.models.plan_models import ChatMessage, Plan, PlanStep
from app.services import plan_service


@pytest.fixture(autouse=True)
def reset_plans():
    plan_service._plans.clear()
    yield
    plan_service._plans.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _two_step_plan(session_id: str = "sid") -> Plan:
    return Plan(
        session_id=session_id,
        goal="test goal",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="POLYGON", status="active"),
            PlanStep(index=1, instruction="Step 2", expected_tool="TRIM", status="pending"),
        ],
        current_index=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_try_advance_matches_and_advances():
    plan = _two_step_plan()
    plan_service._plans["sid"] = plan

    result = plan_service.try_advance("sid", "polygon")  # lowercase — tests normalization

    assert result is not None
    assert plan.steps[0].status == "done"
    assert plan.current_index == 1
    assert plan.steps[1].status == "active"


def test_try_advance_no_match_noop():
    plan = _two_step_plan()
    plan_service._plans["sid"] = plan

    result = plan_service.try_advance("sid", "LINE")

    assert result is None
    assert plan_service._plans["sid"].current_index == 0
    assert plan_service._plans["sid"].steps[0].status == "active"


def test_try_advance_null_expected_tool_requires_manual():
    plan = Plan(
        session_id="sid",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Manual step", expected_tool=None, status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["sid"] = plan

    result = plan_service.try_advance("sid", "ANYTHING")

    assert result is None
    assert plan_service._plans["sid"].current_index == 0
    assert plan_service._plans["sid"].steps[0].status == "active"


def test_advance_manual_unconditional():
    plan = Plan(
        session_id="sid",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="POLYGON", status="active"),
            PlanStep(index=1, instruction="Step 2", expected_tool="POLYGON", status="pending"),
        ],
        current_index=0,
    )
    plan_service._plans["sid"] = plan

    result = plan_service.advance_manual("sid")

    assert result is not None
    assert plan.steps[0].status == "done"
    assert plan.current_index == 1
    assert plan.steps[1].status == "active"


def test_clear_and_has_active_plan():
    plan = Plan(
        session_id="sid",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="LINE", status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["sid"] = plan

    assert plan_service.has_active_plan("sid") is True

    plan_service.clear("sid")

    assert plan_service.has_active_plan("sid") is False

    # A plan where current_index >= len(steps) is also considered inactive
    completed_plan = Plan(
        session_id="sid",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Step 1", expected_tool="LINE", status="done"),
        ],
        current_index=1,
    )
    plan_service._plans["sid"] = completed_plan

    assert plan_service.has_active_plan("sid") is False


def test_generate_plan_parses_json(monkeypatch):
    monkeypatch.setattr(
        plan_service.rag_service,
        "safe_retrieve_for_query",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        plan_service.llm_service,
        "generate_plan_json",
        AsyncMock(
            return_value=[
                {"instruction": "Draw a hexagon", "expected_tool": "polygon"},
                {"instruction": "Extrude it", "expected_tool": None},
            ]
        ),
    )

    plan = asyncio.run(plan_service.generate_plan(None, "sid", "draw a hexagon"))

    assert len(plan.steps) == 2

    step0 = plan.steps[0]
    assert step0.instruction == "Draw a hexagon"
    assert step0.expected_tool == "POLYGON"  # normalized to uppercase
    assert step0.status == "active"

    step1 = plan.steps[1]
    assert step1.expected_tool is None
    assert step1.status == "pending"

    assert plan.current_index == 0
    assert "sid" in plan_service._plans


def test_generate_plan_malformed_json_fallback(monkeypatch):
    monkeypatch.setattr(
        plan_service.llm_service,
        "generate_plan_json",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        plan_service.rag_service,
        "safe_retrieve_for_query",
        AsyncMock(return_value=[]),
    )

    plan = asyncio.run(plan_service.generate_plan(None, "sid", "vague goal"))

    assert plan is not None
    assert len(plan.steps) >= 1


def test_advance_manual_last_step_boundary():
    """advance_manual on the last step increments current_index beyond len(steps) — plan becomes inactive."""
    plan = Plan(
        session_id="sid",
        goal="test",
        steps=[
            PlanStep(index=0, instruction="Only step", expected_tool="LINE", status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["sid"] = plan

    result = plan_service.advance_manual("sid")

    assert result is not None
    assert plan.steps[0].status == "done"
    assert plan.current_index == 1  # == len(steps), plan is now complete
    assert plan_service.has_active_plan("sid") is False


def test_chat_no_plan_triggers_generate(monkeypatch):
    """chat() with no existing plan calls generate_plan and yields the plan summary."""
    monkeypatch.setattr(
        plan_service.rag_service,
        "safe_retrieve_for_query",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        plan_service.llm_service,
        "generate_plan_json",
        AsyncMock(return_value=[{"instruction": "Draw line", "expected_tool": "LINE"}]),
    )

    async def run():
        tokens = []
        async for t in plan_service.chat(None, "sid", "draw a line"):
            tokens.append(t)
        return tokens

    tokens = asyncio.run(run())

    assert len(tokens) >= 1  # yields the plan summary
    assert "sid" in plan_service._plans


def test_chat_existing_plan_streams_tokens(monkeypatch):
    """chat() with an existing plan streams tokens from llm_service.stream_chat."""
    plan = Plan(
        session_id="sid",
        goal="draw hexagon",
        steps=[
            PlanStep(index=0, instruction="Use POLYGON", expected_tool="POLYGON", status="active"),
        ],
        current_index=0,
    )
    plan_service._plans["sid"] = plan

    async def fake_stream_chat(messages, system_prompt, context_docs):
        yield "token1"
        yield " token2"

    monkeypatch.setattr(
        plan_service.rag_service,
        "safe_retrieve_for_query",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        plan_service.llm_service,
        "stream_chat",
        fake_stream_chat,
    )

    async def run():
        tokens = []
        async for t in plan_service.chat(None, "sid", "what does POLYGON do?"):
            tokens.append(t)
        return tokens

    tokens = asyncio.run(run())

    assert tokens == ["token1", " token2"]
    # assistant message appended to plan history
    msgs = plan_service._plans["sid"].messages
    assert msgs[-1].role == "assistant"
    assert msgs[-1].content == "token1 token2"
