"""Whisper transcription via faster-whisper (CTranslate2, fully offline)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .config import Config


class Transcriber:
    """Lazily loads a WhisperModel and reuses it across transcriptions.

    Loading a model is expensive (and may download on first use), so we keep the
    instance around and only rebuild it when the model/device/compute settings
    actually change.
    """

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._model = None
        self._loaded_key: tuple | None = None
        self._lock = threading.Lock()

    def _key(self, cfg: Config) -> tuple:
        return (cfg.model, cfg.device, cfg.compute_type)

    def ensure_loaded(self, cfg: Config, progress: Callable[[str], None] | None = None):
        with self._lock:
            key = self._key(cfg)
            if self._model is not None and key == self._loaded_key:
                return self._model
            if progress:
                progress(f"Loading model “{cfg.model}”…")
            from faster_whisper import WhisperModel

            from .models import repo_id

            device = cfg.device
            compute_type = cfg.compute_type
            if device == "auto":
                device, compute_type = _auto_device(compute_type)
            # A model preset may request a GPU-only compute (e.g. Turbo V3 large ->
            # float16); sanitize so an incompatible device/compute pair can never
            # reach CTranslate2 and crash.
            compute_type = _sanitize_compute(device, compute_type)
            # Resolve through the same repo mapping is_downloaded() uses, so custom
            # aliases (large-v3-turbo, distil-large-v3) load the exact repo we report
            # as cached instead of faster-whisper's own — possibly different — default.
            self._model = WhisperModel(
                repo_id(cfg.model), device=device, compute_type=compute_type
            )
            self._loaded_key = key
            return self._model

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._loaded_key = None

    def transcribe(
        self,
        wav_path: Path,
        cfg: Config,
        progress: Callable[[str], None] | None = None,
    ) -> str:
        model = self.ensure_loaded(cfg, progress)
        if progress:
            progress("Transcribing…")

        language = None if cfg.language in ("", "auto") else cfg.language
        segments, _info = model.transcribe(
            str(wav_path),
            language=language,
            beam_size=max(1, cfg.beam_size),
            temperature=cfg.temperature,
            initial_prompt=cfg.initial_prompt or None,
            vad_filter=cfg.vad_filter,
            no_speech_threshold=cfg.no_speech_threshold,
        )
        text = "".join(seg.text for seg in segments).strip()
        if text and cfg.add_trailing_space:
            text += " "
        return text


def _auto_device(preferred_compute: str) -> tuple[str, str]:
    """Pick CUDA if a working GPU stack is present, else CPU."""
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            ct = preferred_compute if preferred_compute in ("float16", "int8_float16") else "float16"
            return "cuda", ct
    except Exception:
        pass
    ct = preferred_compute if preferred_compute in ("int8", "float32") else "int8"
    return "cpu", ct


# Compute types CTranslate2 actually supports per device.
_CPU_COMPUTES = {"int8", "int16", "float32"}
_GPU_COMPUTES = {"int8", "int8_float16", "float16", "float32"}


def _sanitize_compute(device: str, compute_type: str) -> str:
    """Coerce a compute_type to one valid for ``device`` (never crash on a bad pair)."""
    if device == "cpu":
        if compute_type in _CPU_COMPUTES:
            return compute_type
        return "float32" if compute_type in ("float16", "float32") else "int8"
    # cuda / any GPU
    if compute_type in _GPU_COMPUTES:
        return compute_type
    return "float16"
