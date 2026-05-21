import json
import pytest

from app.db.crud import (
    _affected_rows_from_status,
    _embedding_record_to_dict,
    parse_vector_literal,
    to_vector_literal,
)
from app.db.schema import VECTOR_DIMENSION


def test_to_vector_literal_rejects_invalid_dimension() -> None:
    with pytest.raises(ValueError):
        to_vector_literal([0.1, 0.2])


def test_to_vector_literal_and_parse_round_trip() -> None:
    vector = [0.0] * VECTOR_DIMENSION

    literal = to_vector_literal(vector)
    parsed = parse_vector_literal(literal)

    assert len(parsed) == VECTOR_DIMENSION
    assert parsed == vector


def test_parse_vector_literal_handles_none() -> None:
    assert parse_vector_literal(None) == []


def test_affected_rows_from_status_extracts_count() -> None:
    assert _affected_rows_from_status("DELETE 1") == 1
    assert _affected_rows_from_status("UPDATE 0") == 0


def test_affected_rows_from_status_handles_invalid_value() -> None:
    assert _affected_rows_from_status("") == 0


def test_embedding_record_to_dict_metadata_round_trips() -> None:
    """metadata JSON survives the dict conversion path."""
    metadata = {"source_video": "fillet_basics", "timestamp_start": 42.5, "tags": ["FILLET"]}
    # Simulate what asyncpg returns: metadata already parsed as a dict by asyncpg's JSONB codec
    fake_record = {
        "doc_id": "fillet_basics-0000",
        "source": "video:fillet_basics",
        "content": "some text",
        "embedding_text": "[" + ",".join(["0.0"] * VECTOR_DIMENSION) + "]",
        "metadata": metadata,
        "created_at": None,
    }
    result = _embedding_record_to_dict(fake_record)
    assert result is not None
    assert result["metadata"] == metadata
    assert result["metadata"]["source_video"] == "fillet_basics"
    assert result["metadata"]["tags"] == ["FILLET"]


def test_embedding_record_to_dict_returns_none_for_none() -> None:
    assert _embedding_record_to_dict(None) is None


def test_create_embedding_metadata_json_serializable() -> None:
    """Ensure the metadata dict we'd pass to create_embedding serialises cleanly."""
    metadata = {
        "source_video": "autocad_line",
        "timestamp_start": 10.0,
        "timestamp_end": 70.0,
        "active_tool_hint": "LINE",
        "tags": ["LINE"],
    }
    serialised = json.dumps(metadata)
    recovered = json.loads(serialised)
    assert recovered == metadata
