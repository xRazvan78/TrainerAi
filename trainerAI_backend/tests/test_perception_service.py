import asyncio
import base64
import io
import logging
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.models.perception_models import PerceptionElement


def _make_black_jpeg_b64(width: int = 200, height: int = 200) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (0, 0, 0)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(autouse=True)
def _reset_perception_singletons(monkeypatch):
    import app.services.perception_service as ps

    monkeypatch.setattr(ps, "_ocr_reader", None)
    monkeypatch.setattr(ps, "_yolo_model", None)
    monkeypatch.setattr(ps, "_yolo_loaded", False)
    yield


def test_analyse_frame_heuristic_extracts_command_line(monkeypatch):
    import app.services.perception_service as ps

    stub_ocr = types.SimpleNamespace(
        readtext=lambda region: [((0, 0, 0, 0), "Command: LINE", 0.95)]
    )
    monkeypatch.setattr(ps, "_get_ocr", lambda: stub_ocr)
    monkeypatch.setattr(ps, "_get_yolo", lambda: None)

    b64 = _make_black_jpeg_b64(200, 200)
    result = ps.analyse_frame(b64)

    assert len(result) == 1
    el = result[0]
    assert el.label == "command_line"
    assert "LINE" in el.text
    assert el.bbox[1] == 170  # 200 - 30
    assert el.bbox[3] == 200


def test_analyse_frame_yolo_overrides_heuristic_command_line(monkeypatch):
    import app.services.perception_service as ps

    stub_ocr = types.SimpleNamespace(
        readtext=lambda region: [((0, 0, 0, 0), "LINE", 0.9)]
    )
    monkeypatch.setattr(ps, "_get_ocr", lambda: stub_ocr)

    fake_box = types.SimpleNamespace(
        xyxy=[types.SimpleNamespace(tolist=lambda: [10.0, 10.0, 90.0, 40.0])],
        cls=[0],
        conf=[0.88],
    )
    fake_result = types.SimpleNamespace(boxes=[fake_box])

    class CallableFakeYolo:
        names = {0: "command_line"}

        def __call__(self, frame, conf, verbose):
            return [fake_result]

    monkeypatch.setattr(ps, "_get_yolo", lambda: CallableFakeYolo())

    b64 = _make_black_jpeg_b64(200, 200)
    result = ps.analyse_frame(b64)

    command_line_elements = [e for e in result if e.label == "command_line"]
    assert len(command_line_elements) == 1
    el = command_line_elements[0]
    assert el.bbox == [10, 10, 90, 40]


def test_analyse_frame_decode_failure_returns_empty(caplog):
    import app.services.perception_service as ps

    with caplog.at_level(logging.ERROR, logger="app.services.perception_service"):
        result = ps.analyse_frame("not-base64!!!@@@")

    assert result == []
    assert any(True for r in caplog.records if r.levelno >= logging.ERROR)


def test_analyse_frame_no_weights_skips_yolo_silently(monkeypatch):
    import app.services.perception_service as ps

    monkeypatch.setattr(ps, "_WEIGHTS_PATH", Path("/tmp/nonexistent_autocad.pt"))
    monkeypatch.setattr(ps, "_yolo_loaded", False)
    monkeypatch.setattr(ps, "_yolo_model", None)

    stub_ocr = types.SimpleNamespace(
        readtext=lambda region: [((0, 0, 0, 0), "LINE", 0.9)]
    )
    monkeypatch.setattr(ps, "_get_ocr", lambda: stub_ocr)

    b64 = _make_black_jpeg_b64(200, 200)
    result = ps.analyse_frame(b64)

    command_line_elements = [e for e in result if e.label == "command_line"]
    assert len(command_line_elements) == 1
