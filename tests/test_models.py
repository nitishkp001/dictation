"""Model registry tests."""

from __future__ import annotations

import pytest

from dictux import models


def test_registry_not_empty_and_unique_ids():
    ids = [m.id for m in models.MODELS]
    assert len(ids) >= 5
    assert len(ids) == len(set(ids))


def test_lookup_helpers():
    assert models.get("base") is not None
    assert models.get("does-not-exist") is None


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("base", "Systran/faster-whisper-base"),
        ("large-v3", "Systran/faster-whisper-large-v3"),
        ("large-v3-turbo", "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
        ("distil-large-v3", "Systran/faster-distil-whisper-large-v3"),
    ],
)
def test_repo_id_mapping(model_id, expected):
    assert models._repo_id(model_id) == expected


def test_custom_repo_id_passthrough():
    assert models._repo_id("some/custom-repo") == "some/custom-repo"


def test_sizes_are_positive():
    for m in models.MODELS:
        assert m.size_mb > 0
