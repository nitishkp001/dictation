"""Curated Whisper model catalog.

Mirrors the model line-up of the original OpenSuperWhisper (Turbo V3 large/medium/
small + a Hebrew fine-tune) while staying on faster-whisper (CTranslate2). Where
whisper.cpp shipped separately-quantized ``.bin`` files, CTranslate2 quantizes at
load time, so the three "Turbo V3" tiers share one download and differ only by the
``compute`` preset applied when selected.

faster-whisper resolves each ``repo`` from the Hugging Face Hub and caches it under
~/.cache/huggingface; selecting a model that isn't cached triggers a download.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import try_to_load_from_cache

_TURBO_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"


@dataclass(frozen=True)
class ModelInfo:
    id: str                       # stored in config as cfg.model
    label: str                    # human-friendly name shown in the UI
    repo: str                     # faster-whisper repo id (or local path)
    size_mb: int                  # approximate download size
    note: str
    group: str = "Standard"       # UI grouping
    compute: str | None = None    # compute_type preset applied on selection
    preferred_language: str | None = None
    english_only: bool = False

    @property
    def size_str(self) -> str:
        return f"{self.size_mb / 1000:.1f} GB" if self.size_mb >= 1000 else f"{self.size_mb} MB"

    @property
    def hf_page_url(self) -> str:
        return f"https://huggingface.co/{self.repo}"


# Ordered for the UI. Turbo V3 tiers share the same download (_TURBO_REPO).
MODELS: list[ModelInfo] = [
    # --- Turbo V3 (large-v3-turbo, quantized at load) — matches the original ---
    ModelInfo("turbo-large", "Turbo V3 large", _TURBO_REPO, 1620,
              "High accuracy, best quality.", group="Turbo V3", compute="float16"),
    ModelInfo("turbo-medium", "Turbo V3 medium", _TURBO_REPO, 1620,
              "Balanced speed and accuracy.", group="Turbo V3", compute="int8_float16"),
    ModelInfo("turbo-small", "Turbo V3 small", _TURBO_REPO, 1620,
              "Fastest processing (shares the Turbo V3 download).",
              group="Turbo V3", compute="int8"),
    # --- Standard multilingual Whisper (genuinely different downloads) ---
    ModelInfo("tiny", "Tiny", "Systran/faster-whisper-tiny", 75,
              "Fastest, lowest accuracy. Good for testing."),
    ModelInfo("tiny.en", "Tiny (English)", "Systran/faster-whisper-tiny.en", 75,
              "English-only tiny.", english_only=True),
    ModelInfo("base", "Base", "Systran/faster-whisper-base", 145,
              "Fast, decent accuracy. Solid default."),
    ModelInfo("small", "Small", "Systran/faster-whisper-small", 484,
              "Balanced speed and accuracy."),
    ModelInfo("medium", "Medium", "Systran/faster-whisper-medium", 1530,
              "High accuracy, slower on CPU."),
    ModelInfo("large-v3", "Large v3", "Systran/faster-whisper-large-v3", 3090,
              "Best accuracy, heaviest."),
    # --- Distil (English, near-large quality, faster) ---
    ModelInfo("distil-large-v3", "Distil Large v3", "Systran/faster-distil-whisper-large-v3",
              1520, "Near large-v3 accuracy, ~2x faster.", group="Distil", english_only=True),
    # --- Fine-tuned ---
    ModelInfo("turbo-hebrew", "Turbo V3 Hebrew", "ivrit-ai/whisper-large-v3-turbo-ct2", 1620,
              "Hebrew fine-tune of Turbo V3 by ivrit.ai. Sets the language to Hebrew.",
              group="Fine-tuned", preferred_language="he"),
]

MODELS_BY_ID = {m.id: m for m in MODELS}

# Order of the UI groups.
GROUPS = ["Turbo V3", "Standard", "Distil", "Fine-tuned"]


def get(model_id: str) -> ModelInfo | None:
    return MODELS_BY_ID.get(model_id)


DEFAULT_LANGUAGE = "auto"
DEFAULT_COMPUTE = "int8"


def selection_overrides(model_id: str) -> dict:
    """Config fields a model *forces* when chosen (compute preset, language)."""
    info = MODELS_BY_ID.get(model_id)
    if info is None:
        return {}
    out: dict[str, str] = {}
    if info.compute:
        out["compute_type"] = info.compute
    if info.preferred_language:
        out["language"] = info.preferred_language
    return out


def selection_changes(old_model_id: str | None, new_model_id: str) -> dict:
    """Config changes when switching ``old`` → ``new``, resetting presets left behind.

    A model that declares no preset must not inherit a previous model's forced
    language/compute (e.g. switching away from the Hebrew fine-tune must clear the
    forced ``he`` language rather than leave it stuck).
    """
    old = MODELS_BY_ID.get(old_model_id or "")
    new = MODELS_BY_ID.get(new_model_id)
    changes: dict[str, str] = {"model": new_model_id}

    if new and new.preferred_language:
        changes["language"] = new.preferred_language
    elif old and old.preferred_language:  # leaving a language-forcing model
        changes["language"] = DEFAULT_LANGUAGE

    if new and new.compute:
        changes["compute_type"] = new.compute
    elif old and old.compute:  # leaving a compute-preset model
        changes["compute_type"] = DEFAULT_COMPUTE
    return changes


def models_by_group() -> dict[str, list[ModelInfo]]:
    out: dict[str, list[ModelInfo]] = {g: [] for g in GROUPS}
    for m in MODELS:
        out.setdefault(m.group, []).append(m)
    return {g: ms for g, ms in out.items() if ms}


# Raw whisper aliases faster-whisper understands, mapped to their Systran repos.
_RAW_ALIASES = {
    "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "medium", "medium.en", "large-v3", "large-v2", "large-v1",
}


def repo_id(model_id: str) -> str:
    """Resolve a catalog id (or raw whisper alias / local path) to an HF repo id."""
    info = MODELS_BY_ID.get(model_id)
    if info is not None:
        return info.repo
    if Path(model_id).exists():
        return model_id
    if model_id in _RAW_ALIASES:
        return f"Systran/faster-whisper-{model_id}"
    if model_id == "large-v3-turbo":
        return _TURBO_REPO
    if model_id == "distil-large-v3":
        return "Systran/faster-distil-whisper-large-v3"
    return model_id  # assume a full repo id / local path


def is_downloaded(model_id: str) -> bool:
    """True if the model's weights are already in the HF cache."""
    repo = repo_id(model_id)
    if Path(repo).exists():  # local path
        return True
    hit = try_to_load_from_cache(repo, "model.bin")
    return isinstance(hit, str)
