"""First-run setup wizard: welcome → language → shortcut → model → done."""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, download, hotkey, models
from .config import Config
from .settings_window import _LANGUAGES


class _DlSignals(QObject):
    progress = Signal(float)
    finished = Signal(bool, str)


class OnboardingWindow(QWidget):
    def __init__(self, cfg: Config, on_done: Callable[[Config], None]):
        super().__init__()
        self.cfg = cfg
        self._on_done = on_done
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setMinimumWidth(440)

        self._dl = _DlSignals()
        self._dl.progress.connect(lambda f: self.dl_bar.setValue(int(f * 100)))
        self._dl.finished.connect(self._on_download_finished)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._welcome_page())
        self.stack.addWidget(self._language_page())
        self.stack.addWidget(self._shortcut_page())
        self.stack.addWidget(self._model_page())
        self.stack.addWidget(self._done_page())

        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._go_back)
        self.skip_btn = QPushButton("Skip for now")
        self.skip_btn.setFlat(True)
        self.skip_btn.clicked.connect(self._finish)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self._on_next)

        nav = QHBoxLayout()
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.skip_btn)
        nav.addWidget(self.next_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.stack, 1)
        root.addLayout(nav)
        self._update_nav()

    # -- pages ----------------------------------------------------------------

    def _welcome_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel(f"Welcome to {APP_NAME}")
        title.setStyleSheet("font-size: 18px; font-weight: 500;")
        body = QLabel(
            "Local, private voice-to-text for Linux. Press a hotkey, speak, and your "
            "words are transcribed offline and dropped into the focused app.\n\n"
            "This quick setup gets you ready in four steps."
        )
        body.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(body)
        lay.addStretch(1)
        return w

    def _language_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._heading("Language"))
        lay.addWidget(self._hint("Pick the language you'll dictate in, or leave it on "
                                 "auto-detect."))
        self.lang_combo = QComboBox()
        for label, code in _LANGUAGES:
            self.lang_combo.addItem(label, code)
        idx = self.lang_combo.findData(self.cfg.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        lay.addWidget(self.lang_combo)
        lay.addStretch(1)
        return w

    def _shortcut_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._heading("Recording shortcut"))
        lay.addWidget(self._hint("Bind a key to start/stop recording. On GNOME we can "
                                 "register it for you."))
        self.accel_edit = QLineEdit(self.cfg.gnome_hotkey)
        lay.addWidget(self.accel_edit)
        reg = QPushButton("Register shortcut")
        reg.clicked.connect(self._register_shortcut)
        lay.addWidget(reg)
        self.shortcut_status = QLabel("")
        self.shortcut_status.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(self.shortcut_status)
        if not hotkey.gnome_available():
            lay.addWidget(self._hint("Not on GNOME? Bind `dictux --toggle` to a key in "
                                     "your desktop's keyboard settings."))
        lay.addStretch(1)
        return w

    def _model_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._heading("Download a model"))
        lay.addWidget(self._hint("Runs fully offline. You can add more later in "
                                 "Settings; an undownloaded model also downloads on "
                                 "first use."))
        self.model_combo = QComboBox()
        for m in models.MODELS:
            mark = "✓ " if models.is_downloaded(m.id) else ""
            self.model_combo.addItem(f"{mark}{m.label} · {m.size_str} — {m.note}", m.id)
        idx = self.model_combo.findData(self.cfg.model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        lay.addWidget(self.model_combo)

        self.dl_btn = QPushButton("Download now")
        self.dl_btn.clicked.connect(self._start_download)
        lay.addWidget(self.dl_btn)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setVisible(False)
        lay.addWidget(self.dl_bar)
        self.dl_status = QLabel("")
        self.dl_status.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(self.dl_status)
        lay.addStretch(1)
        return w

    def _done_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._heading("You're all set"))
        lay.addWidget(self._hint(
            "Press your shortcut and start talking. The tray icon (top bar) has the "
            "model menu, settings, and history. Enjoy!"
        ))
        lay.addStretch(1)
        return w

    # -- helpers --------------------------------------------------------------

    def _heading(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 15px; font-weight: 500;")
        return lbl

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: gray;")
        return lbl

    def _register_shortcut(self) -> None:
        accel = self.accel_edit.text().strip()
        try:
            hotkey.install_gnome_hotkey(accel)
            self.shortcut_status.setText(f"Registered {accel}")
        except Exception as e:  # noqa: BLE001
            self.shortcut_status.setText(f"Couldn't register: {e}")

    # -- model download -------------------------------------------------------

    def _start_download(self) -> None:
        model_id = self.model_combo.currentData()
        self.dl_btn.setEnabled(False)
        self.dl_bar.setVisible(True)
        self.dl_bar.setValue(0)
        self.dl_status.setText("Downloading…")

        def worker():
            try:
                download.download_model(model_id, lambda f: self._dl.progress.emit(f))
                self._dl.finished.emit(True, "")
            except Exception as e:  # noqa: BLE001
                self._dl.finished.emit(False, str(e))

        threading.Thread(target=worker, name="onboard-dl", daemon=True).start()

    def _on_download_finished(self, ok: bool, error: str) -> None:
        self.dl_bar.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.dl_status.setText("Downloaded ✓" if ok else f"Failed: {error}")

    # -- navigation -----------------------------------------------------------

    def _on_next(self) -> None:
        if self.stack.currentIndex() >= self.stack.count() - 1:
            self._finish()
        else:
            self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
            self._update_nav()

    def _go_back(self) -> None:
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._update_nav()

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        last = idx == self.stack.count() - 1
        self.back_btn.setEnabled(idx > 0)
        self.skip_btn.setVisible(not last)
        self.next_btn.setText("Get started" if last else "Next")

    def _finish(self) -> None:
        model_id = self.model_combo.currentData()
        kwargs = {
            "language": self.lang_combo.currentData(),   # explicit choice wins
            "gnome_hotkey": self.accel_edit.text().strip() or self.cfg.gnome_hotkey,
            "model": model_id,
            "onboarded": True,
        }
        # Apply the model's compute preset (e.g. Turbo tiers), but not its language —
        # the user picked that on the language step.
        preset = models.selection_overrides(model_id)
        if "compute_type" in preset:
            kwargs["compute_type"] = preset["compute_type"]
        self.cfg = replace(self.cfg, **kwargs)
        self._on_done(self.cfg)
        self.close()
