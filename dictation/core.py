"""Core dictation engine: the record → transcribe → deliver state machine.

Deliberately Qt-free so it can run headless or under any UI. Callers subscribe to
lifecycle callbacks; the tray UI marshals those onto the GUI thread.
"""

from __future__ import annotations

import enum
import threading
import time
from pathlib import Path
from typing import Callable

from . import notifications
from .config import Config
from .output import deliver
from .recorder import Recorder, RecorderError
from .transcriber import Transcriber


class State(enum.Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = State.IDLE
        self._recorder = Recorder(cfg.microphone)
        self._transcriber = Transcriber(cfg)
        self._lock = threading.Lock()

        # UI callbacks (may be reassigned by the tray). Default: no-ops.
        self.on_state_change: Callable[[State], None] = lambda s: None
        self.on_result: Callable[[str, str], None] = lambda text, status: None
        self.on_error: Callable[[str], None] = lambda msg: None
        self.on_status: Callable[[str], None] = lambda msg: None

    # -- state helpers --------------------------------------------------------

    def _set_state(self, state: State) -> None:
        self.state = state
        self.on_state_change(state)

    # -- public control -------------------------------------------------------

    def toggle(self) -> None:
        with self._lock:
            if self.state == State.IDLE:
                self._start_locked()
            elif self.state == State.RECORDING:
                self._stop_and_transcribe_locked()
            # If TRANSCRIBING, ignore — let it finish.

    def start(self) -> None:
        with self._lock:
            if self.state == State.IDLE:
                self._start_locked()

    def stop(self) -> None:
        with self._lock:
            if self.state == State.RECORDING:
                self._stop_and_transcribe_locked()

    def cancel(self) -> None:
        with self._lock:
            if self.state == State.RECORDING:
                self._recorder.cancel()
                self._set_state(State.IDLE)
                self.on_status("Cancelled")

    # -- internals (call with lock held) -------------------------------------

    def _start_locked(self) -> None:
        try:
            self._recorder = Recorder(self.cfg.microphone)
            self._recorder.start()
        except RecorderError as e:
            self.on_error(str(e))
            notifications.error(str(e))
            return
        self._set_state(State.RECORDING)
        self.on_status("Recording…")
        if self.cfg.notifications:
            notifications.notify("Recording… press the hotkey again to stop.",
                                 icon="audio-input-microphone")

    def _stop_and_transcribe_locked(self) -> None:
        wav = self._recorder.stop()
        self._set_state(State.TRANSCRIBING)
        if wav is None:
            self.on_status("No audio captured")
            self._set_state(State.IDLE)
            return
        threading.Thread(
            target=self._transcribe_worker, args=(wav,), name="transcribe", daemon=True
        ).start()

    def _transcribe_worker(self, wav: Path) -> None:
        t0 = time.monotonic()
        try:
            text = self._transcriber.transcribe(wav, self.cfg, progress=self.on_status)
        except Exception as e:  # noqa: BLE001 - surface any backend failure
            self.on_error(f"Transcription failed: {e}")
            notifications.error(f"Transcription failed: {e}")
            self._set_state(State.IDLE)
            return
        finally:
            wav.unlink(missing_ok=True)

        elapsed = time.monotonic() - t0
        if not text:
            self.on_status("No speech detected")
            if self.cfg.notifications:
                notifications.notify("No speech detected.", icon="microphone-sensitivity-muted")
            self._set_state(State.IDLE)
            return

        status = deliver(text, self.cfg)
        self.on_result(text, status)
        if self.cfg.notifications:
            preview = text.strip()
            if len(preview) > 80:
                preview = preview[:77] + "…"
            notifications.notify(f"{preview}\n({status}, {elapsed:.1f}s)",
                                 title="Dictation ✓", icon="emblem-ok")
        self._set_state(State.IDLE)

    # -- config / model -------------------------------------------------------

    def apply_config(self, cfg: Config) -> None:
        """Swap in updated settings; reloads the model lazily on next use."""
        old = self.cfg
        self.cfg = cfg
        if (old.model, old.device, old.compute_type) != (cfg.model, cfg.device, cfg.compute_type):
            self._transcriber.unload()
            self._transcriber = Transcriber(cfg)

    def preload_model(self) -> None:
        """Warm the model in the background so the first transcription is fast."""
        def _warm():
            try:
                self._transcriber.ensure_loaded(self.cfg, progress=self.on_status)
                self.on_status("Ready")
            except Exception as e:  # noqa: BLE001
                self.on_error(f"Model load failed: {e}")
        threading.Thread(target=_warm, name="preload", daemon=True).start()
