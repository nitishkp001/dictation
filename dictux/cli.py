"""Command-line entry point.

Usage:
  dictux                    Launch the tray app (or no-op if already running).
  dictux --toggle           Toggle recording in the running app (bind to a key).
  dictux --start/--stop/--cancel
  dictux --show             Open the main window.
  dictux --file PATH        Transcribe an audio/video file.
  dictux --install-hotkey [ACCEL]   Register the GNOME keyboard shortcut.
  dictux --status           Print whether the app is running.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__, ipc
from .config import Config, ensure_dirs


def _send_or_fail(command: str) -> int:
    if not ipc.is_running():
        print("Dictux is not running. Start it first with `dictux`.", file=sys.stderr)
        return 1
    reply = ipc.send(command)
    if reply and reply != "ok":
        print(reply)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dictux", description="Local voice dictation for Linux.")
    parser.add_argument("--version", action="version", version=f"dictux {__version__}")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--toggle", action="store_true", help="toggle recording")
    g.add_argument("--start", action="store_true", help="start recording")
    g.add_argument("--stop", action="store_true", help="stop and transcribe")
    g.add_argument("--cancel", action="store_true", help="cancel recording")
    g.add_argument("--settings", action="store_true", help="open the settings window")
    g.add_argument("--show", action="store_true", help="open the main window")
    g.add_argument("--file", metavar="PATH", help="transcribe an audio/video file")
    g.add_argument("--quit", action="store_true", help="quit the running app")
    g.add_argument("--status", action="store_true", help="report running state")
    g.add_argument("--install-hotkey", nargs="?", const="", metavar="ACCEL",
                   help="register the GNOME keyboard shortcut")
    args = parser.parse_args(argv)

    ensure_dirs()

    for cmd in ("toggle", "start", "stop", "cancel", "settings", "show", "quit"):
        if getattr(args, cmd):
            return _send_or_fail(cmd)

    if args.file:
        path = os.path.abspath(args.file)
        if not os.path.isfile(path):
            print(f"Not a file: {args.file}", file=sys.stderr)
            return 1
        if not ipc.is_running():
            print("Dictux is not running. Start it first with `dictux`.", file=sys.stderr)
            return 1
        ipc.send(f"file:{path}")
        return 0

    if args.status:
        print("running" if ipc.is_running() else "not running")
        return 0

    if args.install_hotkey is not None:
        from . import hotkey
        cfg = Config.load()
        accel = args.install_hotkey or cfg.gnome_hotkey
        try:
            hotkey.install_gnome_hotkey(accel)
        except Exception as e:  # noqa: BLE001
            print(f"Failed to register shortcut: {e}", file=sys.stderr)
            return 1
        if accel != cfg.gnome_hotkey:
            cfg.gnome_hotkey = accel
            cfg.save()
        print(f"Registered GNOME shortcut '{accel}' → dictux --toggle")
        return 0

    # No command: launch the app.
    if ipc.is_running():
        print("Dictux is already running (check your system tray).")
        return 0
    return _run_app()


def _run_app() -> int:
    cfg = Config.load()
    # Optional evdev global hotkey (non-GNOME desktops).
    evdev_listener = None
    if cfg.evdev_hotkey:
        try:
            from .hotkey import EvdevHotkey

            evdev_listener = EvdevHotkey(cfg.evdev_hotkey, lambda: ipc.send("toggle"))
            evdev_listener.start()
        except Exception:
            evdev_listener = None

    from .tray import TrayApp

    app = TrayApp(cfg)
    try:
        return app.run()
    finally:
        if evdev_listener:
            evdev_listener.stop()


if __name__ == "__main__":
    raise SystemExit(main())
