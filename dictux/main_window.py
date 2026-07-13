"""Main window: searchable recording history, record button, drag-drop files."""

from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, models
from .config import Config
from .core import State
from .history import Recording, RecordingStore


def _relative_time(ts: float) -> str:
    delta = time.time() - ts
    if delta < 45:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return time.strftime("%b %d, %H:%M", time.localtime(ts))


class RecordingCard(QFrame):
    def __init__(self, rec: Recording, on_copy, on_retranscribe, on_delete):
        super().__init__()
        self.rec = rec
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        model_label = models.get(rec.model)
        meta = _relative_time(rec.created_at)
        if rec.duration:
            meta += f" · {rec.duration:.0f}s"
        if model_label:
            meta += f" · {model_label.label}"
        meta_lbl = QLabel(meta)
        meta_lbl.setStyleSheet("color: gray; font-size: 11px;")
        top.addWidget(meta_lbl, 1)

        for text, tip, slot in (
            ("Copy", "Copy to clipboard", lambda: on_copy(self.rec)),
            ("↻", "Re-transcribe with the current model", lambda: on_retranscribe(self.rec)),
            ("✕", "Delete", lambda: on_delete(self.rec)),
        ):
            b = QPushButton(text)
            b.setFlat(True)
            b.setToolTip(tip)
            b.setFixedHeight(22)
            b.clicked.connect(lambda _=False, s=slot: s())
            top.addWidget(b)
        lay.addLayout(top)

        self.text_label = QLabel(rec.text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.text_label)


class MainWindow(QWidget):
    def __init__(
        self,
        cfg: Config,
        store: RecordingStore,
        on_toggle: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_transcribe_file: Callable[[str], None],
        on_retranscribe: Callable[[str], None],
    ):
        super().__init__()
        self.cfg = cfg
        self.store = store
        self._on_toggle = on_toggle
        self._on_open_settings = on_open_settings
        self._on_transcribe_file = on_transcribe_file
        self._on_retranscribe = on_retranscribe

        self.setWindowTitle(APP_NAME)
        self.resize(520, 480)
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        # Header: title + search.
        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 15px; font-weight: 500;")
        header.addWidget(title)
        header.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search transcriptions")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(self.refresh)
        header.addWidget(self.search)
        root.addLayout(header)

        # History list (scrollable).
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, 1)

        self._empty = QLabel(
            "No recordings yet.\nPress your hotkey (Super + \\) or the Record button, "
            "or drop an audio file here."
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("color: gray;")
        root.addWidget(self._empty)

        # Footer: record button + settings.
        footer = QHBoxLayout()
        self.record_btn = QPushButton("● Record")
        self.record_btn.clicked.connect(self._on_toggle)
        footer.addWidget(self.record_btn)
        hint = QLabel("or press Super + \\")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        footer.addWidget(hint)
        footer.addStretch(1)
        settings_btn = QPushButton("Settings…")
        settings_btn.clicked.connect(self._on_open_settings)
        footer.addWidget(settings_btn)
        root.addLayout(footer)

        self.refresh()

    # -- list rendering -------------------------------------------------------

    def refresh(self) -> None:
        # Clear existing cards (keep the trailing stretch).
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recs = self.store.search(self.search.text())
        for i, rec in enumerate(recs):
            card = RecordingCard(rec, self._copy, self._retranscribe, self._delete)
            self._list_layout.insertWidget(i, card)

        has_any = bool(self.store.all())
        self._empty.setVisible(not has_any)
        self._scroll.setVisible(has_any)

    def add_recording(self, _rec: Recording) -> None:
        self.refresh()

    def update_recording(self, _rec_id: str, _text: str) -> None:
        self.refresh()

    def set_state(self, state: State) -> None:
        self.record_btn.setText(
            {State.IDLE: "● Record",
             State.RECORDING: "■ Stop",
             State.TRANSCRIBING: "… Transcribing"}[state]
        )
        self.record_btn.setEnabled(state != State.TRANSCRIBING)

    # -- card actions ---------------------------------------------------------

    def _copy(self, rec: Recording) -> None:
        QGuiApplication.clipboard().setText(rec.text)

    def _retranscribe(self, rec: Recording) -> None:
        self._on_retranscribe(rec.id)

    def _delete(self, rec: Recording) -> None:
        self.store.delete(rec.id)
        self.refresh()

    # -- drag & drop ----------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._on_transcribe_file(path)
        event.acceptProposedAction()
