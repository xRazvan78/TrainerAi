from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ISO_TIMESTAMP_ERROR = "timestamp must be a valid ISO-8601 string"


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)
    timestamp: str
    session_id: str = Field(min_length=1)

    @field_validator("text", "session_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_iso8601_timestamp(cls, value: str) -> str:
        normalized = value.replace("Z", "+00:00")
        if "T" not in value:
            raise ValueError(ISO_TIMESTAMP_ERROR)
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(ISO_TIMESTAMP_ERROR) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(ISO_TIMESTAMP_ERROR)
        return value


class CommandAcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    task_id: str
    session_id: str
    received_at: str
