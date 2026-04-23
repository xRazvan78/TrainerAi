from typing import Any

from pydantic import BaseModel, Field


class SessionSnapshot(BaseModel):
    session_id: str
    active_tool: str | None = None
    command_sequence: list[str] = Field(default_factory=list)
    action_count: int = 0
    current_context_label: str = "command_active"
    skill_score: float | None = None
    verbosity_level: str | None = None


class ContextPacketFoundation(BaseModel):
    task_id: str
    session_id: str
    command_text: str
    command_timestamp: str
    session: SessionSnapshot
    perception_state: dict[str, Any] | None = None
