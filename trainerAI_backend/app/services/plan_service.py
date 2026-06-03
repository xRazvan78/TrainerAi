from __future__ import annotations

import logging
from typing import AsyncIterator

from app.models.plan_models import ChatMessage, Plan, PlanStep
from app.services import llm_service, rag_service

logger = logging.getLogger(__name__)

_plans: dict[str, Plan] = {}
# Per-session index of the step the user is actively working in: set once the
# step's expected tool is detected ("engaged"), and consumed when they switch
# to a different tool. This makes a step complete when the user MOVES ON from
# its tool, not the instant they select it.
_engaged: dict[str, int] = {}


def _normalize_tool(tool: str | None) -> str:
    return (tool or "").strip().upper()


def get_plan(session_id: str) -> Plan | None:
    return _plans.get(session_id)


def has_active_plan(session_id: str) -> bool:
    plan = _plans.get(session_id)
    return plan is not None and plan.current_index < len(plan.steps)


def clear(session_id: str) -> None:
    _plans.pop(session_id, None)
    _engaged.pop(session_id, None)


async def generate_plan(pool, session_id: str, goal: str) -> Plan:
    context_docs_raw = await rag_service.safe_retrieve_for_query(pool, goal)
    context_texts = [d.get("content", "") for d in context_docs_raw]

    raw_steps = await llm_service.generate_plan_json(goal, context_texts)

    if not raw_steps:
        raw_steps = [{"instruction": "Describe your goal in more detail.", "expected_tool": None}]

    steps = [
        PlanStep(
            index=i,
            instruction=s.get("instruction", ""),
            detail=(s.get("detail") or "").strip() or None,
            expected_tool=_normalize_tool(s.get("expected_tool")) or None,
            status="active" if i == 0 else "pending",
        )
        for i, s in enumerate(raw_steps)
    ]

    # Short conversational intro — the steps themselves render as the checklist,
    # so the chat bubble must NOT repeat them (avoids the duplicated text dump).
    plan_message = ChatMessage(
        role="assistant",
        content=(
            f"Here's a {len(steps)}-step plan for that. "
            "Follow the checklist — I'll tick off steps as you go, and you can ask me anything."
        ),
    )

    plan = Plan(
        session_id=session_id,
        goal=goal,
        steps=steps,
        current_index=0,
        messages=[plan_message],
    )
    _plans[session_id] = plan
    _engaged.pop(session_id, None)
    return plan


def try_advance(session_id: str, detected_tool: str | None) -> Plan | None:
    plan = _plans.get(session_id)
    if plan is None or plan.current_index >= len(plan.steps):
        return None

    current_step = plan.steps[plan.current_index]
    if not current_step.expected_tool:
        return None

    detected = _normalize_tool(detected_tool)

    if detected == current_step.expected_tool:
        # User is on the right tool — mark the step engaged but keep it active.
        # It only completes once they move on to a different tool.
        _engaged[session_id] = plan.current_index
        return None

    # A different, real tool is selected. If the current step was engaged,
    # switching away from its tool means the user finished it — advance now.
    if not detected or _engaged.get(session_id) != plan.current_index:
        return None

    _engaged.pop(session_id, None)
    current_step.status = "done"
    plan.current_index += 1
    if plan.current_index < len(plan.steps):
        plan.steps[plan.current_index].status = "active"

    return plan


def advance_manual(session_id: str) -> Plan | None:
    plan = _plans.get(session_id)
    if plan is None or plan.current_index >= len(plan.steps):
        return None

    _engaged.pop(session_id, None)
    plan.steps[plan.current_index].status = "done"
    plan.current_index += 1
    if plan.current_index < len(plan.steps):
        plan.steps[plan.current_index].status = "active"

    return plan


async def chat(pool, session_id: str, text: str) -> AsyncIterator[str]:
    plan = _plans.get(session_id)
    if plan is None:
        plan = await generate_plan(pool, session_id, text)
        yield plan.messages[-1].content if plan.messages else ""
        return

    plan.messages.append(ChatMessage(role="user", content=text))

    context_docs_raw = await rag_service.safe_retrieve_for_query(pool, text)
    context_texts = [d.get("content", "") for d in context_docs_raw]

    current_step = plan.steps[plan.current_index] if plan.current_index < len(plan.steps) else None
    plan_context = (
        f"Goal: {plan.goal}\n"
        f"Current step ({plan.current_index + 1}/{len(plan.steps)}): "
        f"{current_step.instruction if current_step else 'Plan complete'}\n"
        f"Steps:\n"
        + "\n".join(
            f"  {'[done]' if s.status == 'done' else '[active]' if s.status == 'active' else '[pending]'} {s.instruction}"
            for s in plan.steps
        )
    )

    messages = [
        {"role": m.role, "content": m.content}
        for m in plan.messages
    ]

    full_context = [plan_context] + context_texts
    accumulated: list[str] = []
    async for token in llm_service.stream_chat(messages, llm_service._CHAT_SYSTEM_PROMPT, full_context):
        accumulated.append(token)
        yield token

    plan.messages.append(ChatMessage(role="assistant", content="".join(accumulated)))
