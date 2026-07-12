"""Global hotkey support.

Two mechanisms:

1. GNOME custom keybinding (default). We register a shortcut via ``gsettings``
   that runs ``dictux --toggle``. Portable, no special permissions, works on
   Wayland. See :func:`install_gnome_hotkey`.

2. Optional evdev listener (for non-GNOME desktops). Reads key events directly
   from /dev/input — requires the user to be in the ``input`` group. Enabled only
   when ``config.evdev_hotkey`` is set and the ``evdev`` extra is installed.
"""

from __future__ import annotations

import subprocess
import threading
from typing import Callable

# --- GNOME gsettings custom keybinding ---------------------------------------

_BASE = "org.gnome.settings-daemon.plugins.media-keys"
_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictux/"


def _gsettings(*args: str) -> str:
    return subprocess.check_output(["gsettings", *args], text=True).strip()


def _gset(*args: str) -> None:
    subprocess.run(["gsettings", *args], check=True)


def install_gnome_hotkey(accelerator: str, command: str = "dictux --toggle",
                         name: str = "Dictux toggle") -> None:
    """Create/update a GNOME custom shortcut bound to ``accelerator``.

    ``accelerator`` uses GTK syntax, e.g. ``<Super>backslash`` or ``<Ctrl><Alt>d``.
    """
    key = f"{_BASE}.custom-keybinding:{_PATH}"
    # Register the path in the media-keys list (idempotent).
    raw = _gsettings("get", _BASE, "custom-keybindings")
    paths = _parse_str_list(raw)
    if _PATH not in paths:
        paths.append(_PATH)
        _gset("set", _BASE, "custom-keybindings", _format_str_list(paths))
    _gset("set", key, "name", name)
    _gset("set", key, "command", command)
    _gset("set", key, "binding", accelerator)


def remove_gnome_hotkey() -> None:
    raw = _gsettings("get", _BASE, "custom-keybindings")
    paths = [p for p in _parse_str_list(raw) if p != _PATH]
    _gset("set", _BASE, "custom-keybindings", _format_str_list(paths))


def gnome_available() -> bool:
    try:
        subprocess.run(["gsettings", "--version"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _parse_str_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw in ("@as []", "[]", ""):
        return []
    inner = raw.strip("[]")
    out = []
    for part in inner.split(","):
        part = part.strip().strip("'\"")
        if part:
            out.append(part)
    return out


def _format_str_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(f"'{i}'" for i in items) + "]"


# --- Optional evdev listener --------------------------------------------------


class EvdevHotkey:
    """Listens for a key combo across all keyboards and fires a callback.

    ``combo`` is a '+'-joined set of evdev key names, e.g. "KEY_LEFTCTRL+KEY_SPACE".
    """

    def __init__(self, combo: str, on_activate: Callable[[], None]):
        self._combo = {k.strip() for k in combo.split("+") if k.strip()}
        self._on_activate = on_activate
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, name="evdev-hotkey", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        try:
            import evdev
            from evdev import ecodes
        except ImportError:
            return
        from selectors import DefaultSelector, EVENT_READ

        devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
        keyboards = [d for d in devices if ecodes.EV_KEY in d.capabilities()]
        if not keyboards:
            return
        sel = DefaultSelector()
        for d in keyboards:
            sel.register(d, EVENT_READ)
        pressed: set[str] = set()
        active = False
        while self._running:
            for kdev, _ in sel.select(timeout=0.5):
                for event in kdev.fileobj.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    name = ecodes.KEY.get(event.code)
                    if name is None:
                        continue
                    if isinstance(name, list):
                        name = name[0]
                    if event.value == 1:
                        pressed.add(name)
                    elif event.value == 0:
                        pressed.discard(name)
                    if self._combo.issubset(pressed) and not active:
                        active = True
                        self._on_activate()
                    elif not self._combo.issubset(pressed):
                        active = False
