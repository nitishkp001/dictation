"""Output routing tests (session detection + graceful degradation)."""

from __future__ import annotations

from dictux import output
from dictux.config import Config


def test_is_wayland_detection(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert output._is_wayland() is True

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert output._is_wayland() is False


def test_deliver_empty_text():
    assert output.deliver("", Config()) == "nothing to output"


def test_deliver_falls_back_when_no_tools(monkeypatch):
    # No clipboard/typing tools available at all.
    monkeypatch.setattr(output.shutil, "which", lambda name: None)
    cfg = Config(copy_to_clipboard=True, auto_paste=False, auto_type=False)
    status = output.deliver("hello", cfg)
    assert status == "no output method available"


def test_deliver_copies_when_wl_copy_present(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(output.shutil, "which",
                        lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None)
    calls = {}

    def fake_pipe(cmd, text):
        calls["cmd"] = cmd
        calls["text"] = text
        return True

    monkeypatch.setattr(output, "_pipe", fake_pipe)
    cfg = Config(copy_to_clipboard=True, auto_paste=False, auto_type=False)
    status = output.deliver("hello world", cfg)
    assert "copied" in status
    assert calls["cmd"] == ["wl-copy"]
    assert calls["text"] == "hello world"
