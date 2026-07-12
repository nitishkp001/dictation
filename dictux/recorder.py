"""Microphone capture via PipeWire's ``pw-record`` (falls back to ffmpeg/pulse).

Recording writes a 16 kHz mono WAV to a temp file. We stop by sending SIGINT so
the recorder finalizes the WAV header cleanly.
"""

from __future__ import annotations

import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


class RecorderError(RuntimeError):
    pass


def _build_command(target: str, out_path: Path) -> list[str]:
    if shutil.which("pw-record"):
        cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16"]
        if target and target != "default":
            cmd += ["--target", target]
        cmd.append(str(out_path))
        return cmd
    if shutil.which("parec") and shutil.which("ffmpeg"):
        # PulseAudio path: parec raw -> ffmpeg wav
        raise RecorderError("pw-record not found; please install pipewire-utils")
    if shutil.which("ffmpeg"):
        # ALSA fallback
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "alsa", "-i", target if target != "default" else "default",
            "-ac", "1", "-ar", "16000", str(out_path),
        ]
    raise RecorderError("No recorder available. Install pipewire-utils (pw-record) or ffmpeg.")


class Recorder:
    """Start/stop microphone recording to a temp WAV file."""

    def __init__(self, microphone: str = "default"):
        self.microphone = microphone
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._started_at: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if self.is_recording:
            return
        fd, name = tempfile.mkstemp(prefix="dictux-", suffix=".wav")
        Path(name).unlink(missing_ok=True)  # let the recorder create it
        import os
        os.close(fd)
        self._path = Path(name)
        cmd = _build_command(self.microphone, self._path)
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
        except FileNotFoundError as e:
            raise RecorderError(f"Failed to launch recorder: {e}") from e
        self._started_at = time.monotonic()

    def stop(self) -> Path | None:
        """Stop recording and return the WAV path (or None if nothing captured)."""
        if self._proc is None:
            return None
        proc, path = self._proc, self._path
        self._proc = None
        self._path = None
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if path and path.exists() and path.stat().st_size > 1024:
            return path
        if path:
            path.unlink(missing_ok=True)
        return None

    def cancel(self) -> None:
        path = self.stop()
        if path:
            path.unlink(missing_ok=True)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started_at if self.is_recording else 0.0
