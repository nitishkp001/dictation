"""Model download tests (snapshot_download is mocked; no network)."""

from __future__ import annotations

import huggingface_hub

from dictux import download, models


def test_download_short_circuits_when_cached(monkeypatch):
    monkeypatch.setattr(models, "is_downloaded", lambda mid: True)
    called = {"snapshot": False}
    monkeypatch.setattr(
        huggingface_hub, "snapshot_download",
        lambda *a, **k: called.__setitem__("snapshot", True),
    )
    progress = []
    download.download_model("base", progress.append)
    assert called["snapshot"] is False       # already cached -> no fetch
    assert progress[-1] == 1.0               # reports complete


def test_download_invokes_snapshot_for_correct_repo(monkeypatch):
    monkeypatch.setattr(models, "is_downloaded", lambda mid: False)
    monkeypatch.setattr(download, "total_size_bytes", lambda repo: 0)
    seen = {}
    monkeypatch.setattr(
        huggingface_hub, "snapshot_download",
        lambda repo, **k: seen.setdefault("repo", repo),
    )
    progress = []
    download.download_model("turbo-large", progress.append)
    assert seen["repo"] == models._repo_id("turbo-large")
    assert progress[-1] == 1.0
