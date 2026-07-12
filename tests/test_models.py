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
    assert models.repo_id(model_id) == expected


def test_custom_repo_id_passthrough():
    assert models.repo_id("some/custom-repo") == "some/custom-repo"


def test_sizes_are_positive():
    for m in models.MODELS:
        assert m.size_mb > 0


def test_catalog_mirrors_original_turbo_tiers():
    labels = {m.label for m in models.MODELS}
    assert {"Turbo V3 large", "Turbo V3 medium", "Turbo V3 small"} <= labels
    # The three Turbo tiers share one download (same repo).
    turbo = [m for m in models.MODELS if m.group == "Turbo V3"]
    assert len({m.repo for m in turbo}) == 1


def test_hebrew_finetune_present():
    heb = models.get("turbo-hebrew")
    assert heb is not None
    assert heb.preferred_language == "he"
    assert "ivrit" in heb.repo


def test_models_by_group_ordering_and_membership():
    grouped = models.models_by_group()
    assert list(grouped)[0] == "Turbo V3"          # Turbo shown first
    all_ids = {m.id for ms in grouped.values() for m in ms}
    assert all_ids == set(models.MODELS_BY_ID)     # every model appears once


def test_selection_overrides():
    assert models.selection_overrides("turbo-small")["compute_type"] == "int8"
    assert models.selection_overrides("turbo-hebrew")["language"] == "he"
    assert models.selection_overrides("base") == {}   # no presets
    assert models.selection_overrides("nope") == {}


def test_selection_changes_resets_language_leaving_hebrew():
    ch = models.selection_changes("turbo-hebrew", "turbo-large")
    assert ch["language"] == "auto"          # he must not leak to the new model
    assert ch["compute_type"] == "float16"   # new model's own preset applies


def test_selection_changes_forces_hebrew():
    assert models.selection_changes("base", "turbo-hebrew")["language"] == "he"


def test_selection_changes_resets_compute_leaving_turbo():
    ch = models.selection_changes("turbo-small", "base")
    assert ch["compute_type"] == models.DEFAULT_COMPUTE   # reset, base has no preset
    assert "language" not in ch


def test_selection_changes_no_presets():
    assert models.selection_changes("base", "small") == {"model": "small"}


def test_size_str_and_hf_url():
    m = models.get("turbo-large")
    assert m.size_str.endswith("GB")
    assert models.get("base").size_str.endswith("MB")
    assert m.hf_page_url.startswith("https://huggingface.co/")
