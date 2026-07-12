"""IPC server/client round-trip tests over a temp socket."""

from __future__ import annotations

import time

from dictux import ipc


def test_server_client_roundtrip(tmp_path):
    sock = tmp_path / "test.sock"
    received = []

    def handler(cmd: str) -> str:
        received.append(cmd)
        return "pong" if cmd == "ping" else "ok"

    server = ipc.Server(handler, socket_path=sock)
    server.start()
    try:
        assert ipc.is_running(sock) is True
        assert ipc.send("toggle", sock) == "ok"
        time.sleep(0.1)
        assert "toggle" in received
    finally:
        server.stop()

    # Socket cleaned up on stop.
    assert not sock.exists()
    assert ipc.is_running(sock) is False


def test_is_running_false_when_no_socket(tmp_path):
    assert ipc.is_running(tmp_path / "missing.sock") is False


def test_handler_exception_does_not_kill_server(tmp_path):
    sock = tmp_path / "test.sock"

    def handler(cmd: str) -> str:
        if cmd == "ping":
            return "pong"
        raise ValueError("boom")

    server = ipc.Server(handler, socket_path=sock)
    server.start()
    try:
        reply = ipc.send("toggle", sock)
        assert "error" in reply
        # Server still alive afterwards.
        assert ipc.send("ping", sock) == "pong"
    finally:
        server.stop()
