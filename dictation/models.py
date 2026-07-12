"""Curated Whisper model registry.

faster-whisper resolves each ``repo_id`` from the Hugging Face Hub and caches it
under ~/.cache/huggingface. Selecting a model that isn't cached yet triggers the
download automatically on first load — we surface that here so the UI can show
sizes and a "download" affordance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import try_to_load_from_cache


@dataclass(frozen=True)
class ModelInfo:
    id: str          # value passed to faster_whisper.WhisperModel
    label: str       # human-friendly name shown in the UI
    size_mb: int     # approximate download size
    note: str
    english_only: bool = False


# Ordered roughly small -> large. ``id`` values are what faster-whisper accepts:
# short aliases resolve to the official Systran CT2 conversions.
MODELS: list[ModelInfo] = [
    ModelInfo("tiny", "Tiny", 75, "Fastest, lowest accuracy. Good for testing."),
    ModelInfo("tiny.en", "Tiny (English)", 75, "English-only tiny.", english_only=True),
    ModelInfo("base", "Base", 145, "Fast, decent accuracy. Solid default."),
    ModelInfo("base.en", "Base (English)", 145, "English-only base.", english_only=True),
    ModelInfo("small", "Small", 484, "Balanced speed and accuracy."),
    ModelInfo("small.en", "Small (English)", 484, "English-only small.", english_only=True),
    ModelInfo("medium", "Medium", 1530, "High accuracy, slower on CPU."),
    ModelInfo("distil-large-v3", "Distil Large v3", 1520,
              "Near large-v3 accuracy, ~2x faster.", english_only=True),
    ModelInfo("large-v3", "Large v3", 3090, "Best accuracy, heaviest."),
    ModelInfo("large-v3-turbo", "Large v3 Turbo", 1620,
              "Large-v3 quality, much faster. Recommended for quality."),
]

MODELS_BY_ID = {m.id: m for m in MODELS}


def get(model_id: str) -> ModelInfo | None:
    return MODELS_BY_ID.get(model_id)


def _repo_id(model_id: str) -> str:
    """Hugging Face repo id faster-whisper uses for a given alias."""
    aliases = {
        "tiny", "tiny.en", "base", "base.en", "small", "small.en",
        "medium", "medium.en", "large-v3", "large-v2", "large-v1",
    }
    if model_id in aliases:
        return f"Systran/faster-whisper-{model_id}"
    if model_id == "large-v3-turbo":
        return "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    if model_id == "distil-large-v3":
        return "Systran/faster-distil-whisper-large-v3"
    return model_id  # assume a full repo id / local path


def is_downloaded(model_id: str) -> bool:
    """True if the model's weights are already in the HF cache."""
    repo = _repo_id(model_id)
    if Path(repo).exists():  # local path
        return True
    hit = try_to_load_from_cache(repo, "model.bin")
    return isinstance(hit, str)
