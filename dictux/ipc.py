"""Tiny Unix-socket control channel.

The running app listens on a socket; ``dictux --toggle`` (bound to a keyboard
shortcut) connects and sends a one-line command. This is how we get a reliable
"global hotkey" on Wayland without needing privileged input access.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Callable

from .config import SOCKET_PATH, ensure_dirs

COMMANDS = ("toggle", "start", "stop", "cancel", "ping", "quit", "settings")


def send(command: str, socket_path: Path = SOCKET_PATH, timeout: float = 2.0) -> str:
    """Send a command to a running instance; returns its reply (may be empty)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(socket_path))
        s.sendall((command.strip() + "\n").encode())
        try:
            return s.recv(4096).decode().strip()
        except socket.timeout:
            return ""


def is_running(socket_path: Path = SOCKET_PATH) -> bool:
    if not socket_path.exists():
        return False
    try:
        return send("ping", socket_path) == "pong"
    except OSError:
        return False


class Server:
    """Listens for commands and dispatches to a handler on a worker thread."""

    def __init__(self, handler: Callable[[str], str], socket_path: Path = SOCKET_PATH):
        self._handler = handler
        self._path = socket_path
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        ensure_dirs()
        # Clear a stale socket from a previous crash.
        if self._path.exists():
            try:
                if is_running(self._path):
                    raise RuntimeError("Another dictux instance is already running.")
            finally:
                self._path.unlink(missing_ok=True)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(self._path))
        self._sock.listen(8)
        self._sock.settimeout(0.5)
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ipc-server", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(4096).decode().strip()
                except OSError:
                    continue
                reply = ""
                try:
                    reply = self._handler(data) or ""
                except Exception as e:  # never let a bad command kill the server
                    reply = f"error: {e}"
                try:
                    conn.sendall((reply + "\n").encode())
                except OSError:
                    pass

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._path.unlink(missing_ok=True)
