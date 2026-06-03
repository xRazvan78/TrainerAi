from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class PlanStep(BaseModel):
    index: int
    instruction: str
    detail: str | None = None
    expected_tool: str | None = None
    status: Literal["pending", "active", "done"] = "pending"

class Plan(BaseModel):
    session_id: str
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    current_index: int = 0
    messages: list[ChatMessage] = Field(default_factory=list)

class PlanCreateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    goal: str = Field(min_length=1, max_length=2000)

class PlanMessageRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=2000)

class PlanAdvanceRequest(BaseModel):
    session_id: str = Field(min_length=1)

PlanClearRequest = PlanAdvanceRequest
