"""Transcriber model-resolution tests (WhisperModel is mocked; no downloads)."""

from __future__ import annotations

import faster_whisper
import pytest

from dictux import models
from dictux.config import Config
from dictux.transcriber import Transcriber, _sanitize_compute


@pytest.mark.parametrize(
    "device,compute,expected",
    [
        ("cpu", "float16", "float32"),       # GPU-only -> CPU-valid, keeps quality
        ("cpu", "int8_float16", "int8"),     # GPU-only -> CPU-valid
        ("cpu", "int8", "int8"),
        ("cpu", "float32", "float32"),
        ("cuda", "int16", "float16"),        # CPU-only -> GPU-valid
        ("cuda", "float16", "float16"),
        ("cuda", "int8", "int8"),
    ],
)
def test_sanitize_compute(device, compute, expected):
    assert _sanitize_compute(device, compute) == expected


def test_ensure_loaded_resolves_repo_id(monkeypatch):
    """Custom aliases must load the same repo id that is_downloaded() checks."""
    captured = {}

    class FakeModel:
        def __init__(self, model_id, device=None, compute_type=None):
            captured["id"] = model_id
            captured["device"] = device
            captured["compute_type"] = compute_type

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeModel)

    cfg = Config(model="large-v3-turbo", device="cpu", compute_type="int8")
    Transcriber(cfg).ensure_loaded(cfg)

    assert captured["id"] == models.repo_id("large-v3-turbo")
    assert captured["device"] == "cpu"
    assert captured["compute_type"] == "int8"


def test_standard_alias_still_resolves(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        faster_whisper, "WhisperModel",
        lambda mid, **kw: captured.setdefault("id", mid),
    )
    cfg = Config(model="base", device="cpu", compute_type="int8")
    Transcriber(cfg).ensure_loaded(cfg)
    assert captured["id"] == models.repo_id("base")
