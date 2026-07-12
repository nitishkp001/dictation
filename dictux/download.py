"""Download Whisper models from the Hugging Face Hub with progress reporting.

faster-whisper would download a model lazily on first load, but that gives no
feedback. This fetches a model's snapshot up front and reports a 0..1 fraction so
the settings UI can show a progress bar.
"""

from __future__ import annotations

from typing import Callable

from . import models

ProgressCb = Callable[[float], None]


def total_size_bytes(repo: str) -> int:
    """Best-effort total download size for a repo (0 if it can't be determined)."""
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repo, files_metadata=True)
        return sum(s.size or 0 for s in (info.siblings or []))
    except Exception:
        return 0


def download_model(model_id: str, progress_cb: ProgressCb | None = None) -> None:
    """Download a catalog model into the HF cache, reporting fractional progress.

    Safe to call for an already-cached model (returns quickly at 100%).
    """
    if models.is_downloaded(model_id):
        if progress_cb:
            progress_cb(1.0)
        return

    repo = models._repo_id(model_id)
    total = total_size_bytes(repo)
    done = {"n": 0}

    from huggingface_hub import snapshot_download
    from tqdm.auto import tqdm as _tqdm

    class _ReportingTqdm(_tqdm):
        # huggingface_hub creates one of these per file; sum their updates.
        def update(self, n=0):
            result = super().update(n)
            if n and progress_cb and total:
                done["n"] += n
                progress_cb(min(done["n"] / total, 0.999))
            return result

    # Only the weights + small config/tokenizer files are needed for inference.
    snapshot_download(
        repo,
        allow_patterns=["*.bin", "*.json", "*.txt", "*.model", "tokenizer*"],
        tqdm_class=_ReportingTqdm,
    )
    if progress_cb:
        progress_cb(1.0)
