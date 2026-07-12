"""Recorder command-construction tests (no actual audio capture)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dictux import recorder
from dictux.recorder import RecorderError, _build_command


def test_pw_record_command(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which",
                        lambda name: "/usr/bin/pw-record" if name == "pw-record" else None)
    cmd = _build_command("default", Path("/tmp/out.wav"))
    assert cmd[0] == "pw-record"
    assert "16000" in cmd
    assert cmd[-1] == "/tmp/out.wav"
    assert "--target" not in cmd  # default mic -> no explicit target


def test_pw_record_with_target(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which",
                        lambda name: "/usr/bin/pw-record" if name == "pw-record" else None)
    cmd = _build_command("alsa_input.usb-Mic", Path("/tmp/out.wav"))
    assert "--target" in cmd
    assert "alsa_input.usb-Mic" in cmd


def test_ffmpeg_fallback(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which",
                        lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    cmd = _build_command("default", Path("/tmp/out.wav"))
    assert cmd[0] == "ffmpeg"
    assert "alsa" in cmd


def test_no_recorder_raises(monkeypatch):
    monkeypatch.setattr(recorder.shutil, "which", lambda name: None)
    with pytest.raises(RecorderError):
        _build_command("default", Path("/tmp/out.wav"))
