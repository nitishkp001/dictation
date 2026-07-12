"""Download Whisper models from the Hugging Face Hub with progress reporting.

faster-whisper would download a model lazily on first load, but that gives no
feedback. This fetches a model's snapshot up front and reports a 0..1 fraction so
the settings UI can show a progress bar.
"""

from __future__ import annotations

from typing import Callable

from . import models

ProgressCb = Callable[[float], None]


def download_model(model_id: str, progress_cb: ProgressCb | None = None) -> None:
    """Download a catalog model into the HF cache, reporting fractional progress.

    Safe to call for an already-cached model (returns quickly at 100%).
    """
    if models.is_downloaded(model_id):
        if progress_cb:
            progress_cb(1.0)
        return

    repo = models.repo_id(model_id)
    state = {"frac": 0.0}

    from huggingface_hub import snapshot_download
    from tqdm.auto import tqdm as _tqdm

    class _ReportingTqdm(_tqdm):
        """Report progress from the byte-tracking bar using its own ``n``/``total``.

        snapshot_download uses ``tqdm_class`` for its aggregate bars, and across hub
        versions that may be a byte bar or a file-count bar. We key off ``unit`` so
        we always report bytes (not "3 of 4 files"), and only ever move forward.
        """

        def update(self, n=0):
            result = super().update(n)
            if progress_cb and self.total and getattr(self, "unit", "") in ("B", "iB"):
                frac = min(self.n / self.total, 0.999)
                if frac > state["frac"]:
                    state["frac"] = frac
                    progress_cb(frac)
            return result

    # Only the weights + small config/tokenizer files are needed for inference.
    snapshot_download(
        repo,
        allow_patterns=["*.bin", "*.json", "*.txt", "*.model", "tokenizer*"],
        tqdm_class=_ReportingTqdm,
    )
    if progress_cb:
        progress_cb(1.0)
