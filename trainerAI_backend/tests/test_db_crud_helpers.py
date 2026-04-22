import pytest

from app.db.crud import _affected_rows_from_status, parse_vector_literal, to_vector_literal
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
