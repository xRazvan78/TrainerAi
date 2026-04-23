import hashlib

from app.db.schema import VECTOR_DIMENSION


def _hash_to_unit_interval(token: str) -> float:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    number = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return number / float(2**64 - 1)


def embed_text(text: str) -> list[float]:
    # Phase 3 scaffold: deterministic local embedding without external model dependency.
    cleaned = text.strip().lower()
    if not cleaned:
        cleaned = "empty"

    values = []
    for index in range(VECTOR_DIMENSION):
        token = f"{cleaned}|{index}"
        values.append(_hash_to_unit_interval(token))
    return values
