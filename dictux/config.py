"""Persistent configuration stored as JSON under the XDG config dir."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from platformdirs import user_config_dir, user_runtime_dir, user_state_dir

from . import APP_ID

CONFIG_DIR = Path(user_config_dir(APP_ID))
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_DIR = Path(user_state_dir(APP_ID))
RUNTIME_DIR = Path(user_runtime_dir(APP_ID))
SOCKET_PATH = RUNTIME_DIR / "dictux.sock"


@dataclass
class Config:
    """User settings. Field names double as JSON keys."""

    # Model / transcription
    model: str = "base"                 # faster-whisper model id (see models.py)
    compute_type: str = "int8"          # int8 | int8_float16 | float16 | float32
    device: str = "cpu"                 # cpu | cuda | auto
    language: str = "auto"              # ISO code, or "auto" for detection
    beam_size: int = 5
    temperature: float = 0.0
    initial_prompt: str = ""
    vad_filter: bool = True             # drop non-speech with Silero VAD
    no_speech_threshold: float = 0.6

    # Audio
    microphone: str = "default"         # PipeWire target node, or "default"

    # Output behaviour
    copy_to_clipboard: bool = True
    auto_paste: bool = False            # simulate Ctrl+V after copy (needs ydotool/wtype)
    auto_type: bool = False             # type char-by-char (needs ydotool)
    add_trailing_space: bool = True

    # Feedback
    notifications: bool = True
    sound_on_start: bool = False
    show_indicator: bool = True         # floating recording indicator overlay

    # Hotkey
    gnome_hotkey: str = "<Super>backslash"   # bound via gsettings on install
    evdev_hotkey: str = ""              # e.g. "KEY_LEFTCTRL+KEY_SPACE" (optional)
    hold_to_record: bool = False

    def save(self) -> None:
        _save(self)

    @classmethod
    def load(cls) -> "Config":
        return _load(cls)


_lock = threading.Lock()


def _load(cls):
    if not CONFIG_PATH.exists():
        cfg = cls()
        _save(cfg)
        return cfg
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        data = {}
    known = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in known}
    return cls(**filtered)


def _save(cfg) -> None:
    with _lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(cfg), indent=2))
        tmp.replace(CONFIG_PATH)


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, STATE_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
