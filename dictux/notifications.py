"""Desktop notifications via notify-send, with a no-op fallback."""

from __future__ import annotations

import shutil
import subprocess

from . import APP_NAME

_HAVE = shutil.which("notify-send") is not None
_last_id_supported = None


def notify(message: str, title: str = APP_NAME, urgency: str = "low",
           icon: str = "audio-input-microphone") -> None:
    if not _HAVE:
        return
    try:
        subprocess.Popen(
            ["notify-send", "-a", APP_NAME, "-u", urgency, "-i", icon, title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def error(message: str) -> None:
    notify(message, title=f"{APP_NAME} — error", urgency="critical", icon="dialog-error")
