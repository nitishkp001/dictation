"""Deliver transcribed text: clipboard, auto-paste, or direct typing.

Wayland restricts synthetic input, so behaviour is layered:
  * clipboard  -> wl-copy (Wayland) / xclip / xsel
  * auto-paste -> copy, then simulate Ctrl+V via ydotool / wtype / xdotool
  * auto-type  -> type the text directly via ydotool / wtype / xdotool
Whatever isn't available degrades gracefully to clipboard-only.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .config import Config


def _is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(
        os.environ.get("WAYLAND_DISPLAY")
    )


def copy_to_clipboard(text: str) -> bool:
    if _is_wayland() and shutil.which("wl-copy"):
        return _pipe(["wl-copy"], text)
    if shutil.which("xclip"):
        return _pipe(["xclip", "-selection", "clipboard"], text)
    if shutil.which("xsel"):
        return _pipe(["xsel", "--clipboard", "--input"], text)
    return False


def _pipe(cmd: list[str], text: str) -> bool:
    try:
        p = subprocess.run(cmd, input=text.encode(), timeout=5)
        return p.returncode == 0
    except Exception:
        return False


def _type_text(text: str) -> bool:
    if shutil.which("ydotool"):
        try:
            subprocess.run(["ydotool", "type", "--", text], timeout=30, check=True)
            return True
        except Exception:
            pass
    if _is_wayland() and shutil.which("wtype"):
        try:
            subprocess.run(["wtype", "--", text], timeout=30, check=True)
            return True
        except Exception:
            pass
    if not _is_wayland() and shutil.which("xdotool"):
        try:
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text],
                           timeout=30, check=True)
            return True
        except Exception:
            pass
    return False


def _paste_shortcut() -> bool:
    if shutil.which("ydotool"):
        try:
            # 29=LEFTCTRL 47=V ; :1 press :0 release
            subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                           timeout=5, check=True)
            return True
        except Exception:
            pass
    if _is_wayland() and shutil.which("wtype"):
        try:
            subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], timeout=5, check=True)
            return True
        except Exception:
            pass
    if not _is_wayland() and shutil.which("xdotool"):
        try:
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                           timeout=5, check=True)
            return True
        except Exception:
            pass
    return False


def deliver(text: str, cfg: Config) -> str:
    """Route text according to config. Returns a short human-readable status."""
    if not text:
        return "nothing to output"

    statuses = []
    copied = False
    if cfg.copy_to_clipboard or cfg.auto_paste:
        copied = copy_to_clipboard(text)
        if copied:
            statuses.append("copied")

    if cfg.auto_type:
        if _type_text(text):
            statuses.append("typed")
        else:
            statuses.append("type unavailable")
    elif cfg.auto_paste:
        import time
        time.sleep(0.12)  # let the clipboard settle before paste
        if _paste_shortcut():
            statuses.append("pasted")
        else:
            statuses.append("paste unavailable")

    if not statuses:
        # Last resort so the text isn't lost.
        if copy_to_clipboard(text):
            statuses.append("copied")
    return ", ".join(statuses) or "no output method available"
