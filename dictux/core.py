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
from .history import Recording, RecordingStore
from .output import deliver
from .recorder import Recorder, RecorderError
from .transcriber import Transcriber


class State(enum.Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"


class Engine:
    def __init__(self, cfg: Config, store: RecordingStore | None = None):
        self.cfg = cfg
        self.store = store
        self.state = State.IDLE
        self._recorder = Recorder(cfg.microphone)
        self._transcriber = Transcriber(cfg)
        self._lock = threading.Lock()

        # UI callbacks (may be reassigned by the tray). Default: no-ops.
        self.on_state_change: Callable[[State], None] = lambda s: None
        self.on_result: Callable[[str, str], None] = lambda text, status: None
        self.on_error: Callable[[str], None] = lambda msg: None
        self.on_status: Callable[[str], None] = lambda msg: None
        self.on_recording: Callable[[Recording], None] = lambda rec: None
        self.on_retranscribed: Callable[[str, str], None] = lambda rec_id, text: None

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
            wav.unlink(missing_ok=True)
            self.on_error(f"Transcription failed: {e}")
            notifications.error(f"Transcription failed: {e}")
            self._set_state(State.IDLE)
            return

        elapsed = time.monotonic() - t0
        if not text:
            wav.unlink(missing_ok=True)
            self.on_status("No speech detected")
            if self.cfg.notifications:
                notifications.notify("No speech detected.", icon="microphone-sensitivity-muted")
            self._set_state(State.IDLE)
            return

        status = deliver(text, self.cfg)
        self.on_result(text, status)
        self._save_recording(text, elapsed, audio=wav)  # copies audio, then we remove temp
        wav.unlink(missing_ok=True)
        if self.cfg.notifications:
            preview = text.strip()
            if len(preview) > 80:
                preview = preview[:77] + "…"
            notifications.notify(f"{preview}\n({status}, {elapsed:.1f}s)",
                                 title="Dictux ✓", icon="emblem-ok")
        self._set_state(State.IDLE)

    def _save_recording(self, text: str, duration: float, audio: Path | None = None,
                        source: Path | None = None) -> None:
        if self.store is None:
            return
        rec = Recording(text=text, duration=duration, model=self.cfg.model)
        if audio is not None:
            rec.audio_path = self.store.persist_audio(audio, rec.id)
        elif source is not None:
            rec.audio_path = str(source)
        self.store.add(rec)
        self.on_recording(rec)

    # -- file transcription (drag-drop / CLI) --------------------------------

    def transcribe_file(self, path) -> None:
        p = Path(path)
        if not p.exists():
            self.on_error(f"File not found: {p}")
            return
        threading.Thread(
            target=self._file_worker, args=(p,), name="transcribe-file", daemon=True
        ).start()

    def _file_worker(self, path: Path) -> None:
        self.on_status(f"Transcribing {path.name}…")
        t0 = time.monotonic()
        try:
            text = self._transcriber.transcribe(path, self.cfg, progress=self.on_status)
        except Exception as e:  # noqa: BLE001
            self.on_error(f"Transcription failed: {e}")
            return
        elapsed = time.monotonic() - t0
        if not text:
            self.on_status(f"No speech detected in {path.name}")
            return
        self.on_result(text, f"transcribed {path.name}")
        self._save_recording(text, elapsed, source=path)
        if self.cfg.notifications:
            notifications.notify(f"Transcribed {path.name}", title="Dictux ✓", icon="emblem-ok")

    # -- re-transcription (history action) -----------------------------------

    def retranscribe(self, rec_id: str) -> None:
        if self.store is None:
            return
        rec = self.store.get(rec_id)
        if rec is None or not rec.audio_path or not Path(rec.audio_path).exists():
            self.on_error("No stored audio to re-transcribe.")
            return
        threading.Thread(
            target=self._retranscribe_worker, args=(rec_id, Path(rec.audio_path)),
            name="retranscribe", daemon=True,
        ).start()

    def _retranscribe_worker(self, rec_id: str, audio: Path) -> None:
        self.on_status("Re-transcribing…")
        try:
            text = self._transcriber.transcribe(audio, self.cfg, progress=self.on_status)
        except Exception as e:  # noqa: BLE001
            self.on_error(f"Re-transcription failed: {e}")
            return
        if text and self.store is not None:
            self.store.update_text(rec_id, text)
            self.on_retranscribed(rec_id, text)
            self.on_status("Re-transcribed")

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
