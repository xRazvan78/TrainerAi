from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ISO_TIMESTAMP_ERROR = "timestamp must be a valid ISO-8601 string"


class PerceptionElement(BaseModel):
    label: str = Field(min_length=1)
    bbox: list[int] | None = Field(default=None, min_length=4, max_length=4)
    text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value

        x1, y1, x2, y2 = value
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must satisfy x2 > x1 and y2 > y1")
        return value


class PerceptionStateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    timestamp: str
    elements: list[PerceptionElement] = Field(default_factory=list)
    source: str = "perception_pipeline"
    frame_hash: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session_id must not be blank")
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


class PerceptionStatePersistedResponse(BaseModel):
    status: Literal["persisted"] = "persisted"
    perception_id: int
    session_id: str
    observed_at: str
