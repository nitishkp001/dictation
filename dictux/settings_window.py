"""Settings window (Qt): model, audio, output, hotkey and transcription options."""

from __future__ import annotations

import threading
from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import download, hotkey, models
from .config import Config


class _DownloadSignals(QObject):
    progress = Signal(str, float)      # (model_id, fraction)
    finished = Signal(str, bool, str)  # (model_id, ok, error)

_LANGUAGES = [
    ("Auto-detect", "auto"), ("English", "en"), ("Spanish", "es"), ("French", "fr"),
    ("German", "de"), ("Italian", "it"), ("Portuguese", "pt"), ("Dutch", "nl"),
    ("Russian", "ru"), ("Hindi", "hi"), ("Japanese", "ja"), ("Chinese", "zh"),
    ("Korean", "ko"), ("Arabic", "ar"), ("Hebrew", "he"), ("Turkish", "tr"),
    ("Polish", "pl"), ("Ukrainian", "uk"),
]

_COMPUTE_TYPES = ["int8", "int8_float16", "float16", "float32"]
_DEVICES = ["cpu", "cuda", "auto"]


class SettingsWindow(QWidget):
    def __init__(self, cfg: Config, on_apply: Callable[[Config], None]):
        super().__init__()
        self.cfg = cfg
        self._on_apply = on_apply
        self.setWindowTitle("Dictux — Settings")
        self.setMinimumWidth(460)

        tabs = QTabWidget(self)
        tabs.addTab(self._model_tab(), "Model")
        tabs.addTab(self._audio_output_tab(), "Audio & Output")
        tabs.addTab(self._hotkey_tab(), "Hotkey")
        tabs.addTab(self._advanced_tab(), "Advanced")
        tabs.addTab(self._history_tab(), "History")

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.hide)

        buttons = QHBoxLayout()
        buttons.addWidget(self.status_label)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        buttons.addWidget(save_btn)

        root = QVBoxLayout(self)
        root.addWidget(tabs)
        root.addLayout(buttons)

    # -- tabs -----------------------------------------------------------------

    def _model_tab(self) -> QWidget:
        self._dl_signals = _DownloadSignals()
        self._dl_signals.progress.connect(self._on_download_progress)
        self._dl_signals.finished.connect(self._on_download_finished)
        self._model_rows: dict[str, dict] = {}
        self._selected_model_id = self.cfg.model
        self._model_group = QButtonGroup(self)
        self._model_group.setExclusive(True)

        w = QWidget()
        outer = QVBoxLayout(w)

        # Scrollable list of models, grouped like the original app.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setSpacing(4)
        for group, items in models.models_by_group().items():
            header = QLabel(group)
            header.setStyleSheet("font-weight: bold; margin-top: 6px;")
            vbox.addWidget(header)
            for m in items:
                vbox.addWidget(self._model_row(m))
        vbox.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Language selector (below the model list).
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language"))
        self.lang_combo = QComboBox()
        for label, code in _LANGUAGES:
            self.lang_combo.addItem(label, code)
        self._select_combo(self.lang_combo, self.cfg.language)
        lang_row.addWidget(self.lang_combo, 1)
        outer.addLayout(lang_row)

        note = QLabel("Models are cached under ~/.cache/huggingface. Selecting a model "
                      "downloads it if needed; an undownloaded model also downloads on "
                      "first use.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        outer.addWidget(note)
        return w

    def _model_row(self, m: models.ModelInfo) -> QWidget:
        row = QFrame()
        row.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(row)
        lay.setContentsMargins(8, 6, 8, 6)

        top = QHBoxLayout()
        radio = QRadioButton(f"{m.label}  ·  {m.size_str}")
        radio.setChecked(m.id == self._selected_model_id)
        radio.toggled.connect(lambda on, mid=m.id: self._on_model_selected(mid) if on else None)
        self._model_group.addButton(radio)
        top.addWidget(radio, 1)

        hf = QPushButton("HF ↗")
        hf.setFlat(True)
        hf.setToolTip(m.hf_page_url)
        hf.clicked.connect(lambda _=False, url=m.hf_page_url: QDesktopServices.openUrl(QUrl(url)))
        top.addWidget(hf)

        dl_btn = QPushButton()
        dl_btn.clicked.connect(lambda _=False, mid=m.id: self._start_download(mid))
        top.addWidget(dl_btn)
        lay.addLayout(top)

        note = QLabel(m.note)
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(note)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setVisible(False)
        bar.setTextVisible(True)
        lay.addWidget(bar)

        self._model_rows[m.id] = {"radio": radio, "button": dl_btn, "bar": bar}
        self._refresh_download_button(m.id)
        return row

    def _refresh_download_button(self, model_id: str) -> None:
        row = self._model_rows.get(model_id)
        if not row:
            return
        if models.is_downloaded(model_id):
            row["button"].setText("✓ Downloaded")
            row["button"].setEnabled(False)
        else:
            row["button"].setText("⬇ Download")
            row["button"].setEnabled(True)

    def _on_model_selected(self, model_id: str) -> None:
        # Compute the transition from the previously selected model so a preset the
        # old model forced (e.g. Hebrew's language) is reset if the new one doesn't.
        changes = models.selection_changes(self._selected_model_id, model_id)
        self._selected_model_id = model_id
        if "compute_type" in changes:
            self.compute_combo.setCurrentText(changes["compute_type"])
        if "language" in changes:
            self._select_combo(self.lang_combo, changes["language"])

    def _start_download(self, model_id: str) -> None:
        row = self._model_rows.get(model_id)
        if not row:
            return
        row["button"].setEnabled(False)
        row["button"].setText("Downloading…")
        row["bar"].setVisible(True)
        row["bar"].setValue(0)

        def worker():
            try:
                download.download_model(
                    model_id,
                    lambda frac: self._dl_signals.progress.emit(model_id, frac),
                )
                self._dl_signals.finished.emit(model_id, True, "")
            except Exception as e:  # noqa: BLE001
                self._dl_signals.finished.emit(model_id, False, str(e))

        threading.Thread(target=worker, name=f"dl-{model_id}", daemon=True).start()
        self.set_status(f"Downloading {model_id}…")

    def _on_download_progress(self, model_id: str, frac: float) -> None:
        row = self._model_rows.get(model_id)
        if row:
            row["bar"].setValue(int(frac * 100))

    def _on_download_finished(self, model_id: str, ok: bool, error: str) -> None:
        row = self._model_rows.get(model_id)
        if row:
            row["bar"].setVisible(False)
        if ok:
            self._refresh_download_button(model_id)
            # Turbo tiers share a download — refresh their buttons too.
            for other in models.MODELS:
                if other.repo == models.repo_id(model_id):
                    self._refresh_download_button(other.id)
            self.set_status(f"Downloaded {model_id}")
        else:
            if row:
                row["button"].setEnabled(True)
                row["button"].setText("⬇ Download")
            self.set_status(f"Download failed: {error}")

    def _audio_output_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)

        audio_box = QGroupBox("Audio")
        audio_form = QFormLayout(audio_box)
        self.mic_edit = QLineEdit(self.cfg.microphone)
        self.mic_edit.setPlaceholderText("default (or a PipeWire node name)")
        audio_form.addRow("Microphone", self.mic_edit)
        outer.addWidget(audio_box)

        out_box = QGroupBox("Output")
        out_form = QFormLayout(out_box)
        self.copy_check = QCheckBox("Copy transcription to clipboard")
        self.copy_check.setChecked(self.cfg.copy_to_clipboard)
        self.paste_check = QCheckBox("Auto-paste into focused app (needs ydotool/wtype)")
        self.paste_check.setChecked(self.cfg.auto_paste)
        self.type_check = QCheckBox("Type text directly instead of paste (needs ydotool)")
        self.type_check.setChecked(self.cfg.auto_type)
        self.space_check = QCheckBox("Add a trailing space")
        self.space_check.setChecked(self.cfg.add_trailing_space)
        for c in (self.copy_check, self.paste_check, self.type_check, self.space_check):
            out_form.addRow(c)
        outer.addWidget(out_box)

        fb_box = QGroupBox("Feedback")
        fb_form = QFormLayout(fb_box)
        self.notif_check = QCheckBox("Desktop notifications")
        self.notif_check.setChecked(self.cfg.notifications)
        fb_form.addRow(self.notif_check)
        outer.addWidget(fb_box)

        outer.addStretch(1)
        return w

    def _hotkey_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.gnome_hotkey_edit = QLineEdit(self.cfg.gnome_hotkey)
        self.gnome_hotkey_edit.setPlaceholderText("<Super>backslash")
        form.addRow("GNOME shortcut (GTK syntax)", self.gnome_hotkey_edit)

        apply_btn = QPushButton("Register GNOME shortcut")
        apply_btn.clicked.connect(self._register_gnome_hotkey)
        form.addRow(apply_btn)

        if not hotkey.gnome_available():
            warn = QLabel("gsettings not found — on non-GNOME desktops bind "
                          "`dictux --toggle` to a key in your DE's keyboard settings.")
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b26a00;")
            form.addRow(warn)

        self.evdev_edit = QLineEdit(self.cfg.evdev_hotkey)
        self.evdev_edit.setPlaceholderText("optional, e.g. KEY_LEFTCTRL+KEY_SPACE")
        form.addRow("evdev combo (optional)", self.evdev_edit)

        note = QLabel("The shortcut runs `dictux --toggle`, which starts/stops "
                      "recording in this running app.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(note)
        return w

    def _advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.device_combo = QComboBox()
        self.device_combo.addItems(_DEVICES)
        self.device_combo.setCurrentText(self.cfg.device)
        form.addRow("Device", self.device_combo)

        self.compute_combo = QComboBox()
        self.compute_combo.addItems(_COMPUTE_TYPES)
        self.compute_combo.setCurrentText(self.cfg.compute_type)
        form.addRow("Compute type", self.compute_combo)

        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(self.cfg.beam_size)
        form.addRow("Beam size", self.beam_spin)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.cfg.temperature)
        form.addRow("Temperature", self.temp_spin)

        self.nospeech_spin = QDoubleSpinBox()
        self.nospeech_spin.setRange(0.0, 1.0)
        self.nospeech_spin.setSingleStep(0.05)
        self.nospeech_spin.setValue(self.cfg.no_speech_threshold)
        form.addRow("No-speech threshold", self.nospeech_spin)

        self.vad_check = QCheckBox("Voice-activity filter (drop silence)")
        self.vad_check.setChecked(self.cfg.vad_filter)
        form.addRow(self.vad_check)

        self.prompt_edit = QLineEdit(self.cfg.initial_prompt)
        self.prompt_edit.setPlaceholderText("Optional bias prompt / vocabulary")
        form.addRow("Initial prompt", self.prompt_edit)
        return w

    def _history_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        return w

    # -- helpers --------------------------------------------------------------

    def _select_combo(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _register_gnome_hotkey(self) -> None:
        accel = self.gnome_hotkey_edit.text().strip()
        try:
            hotkey.install_gnome_hotkey(accel)
            self.set_status(f"Registered {accel}")
        except Exception as e:  # noqa: BLE001
            self.set_status(f"Failed: {e}")

    def _collect(self) -> Config:
        return replace(
            self.cfg,
            model=self._selected_model_id,
            device=self.device_combo.currentText(),
            compute_type=self.compute_combo.currentText(),
            language=self.lang_combo.currentData(),
            microphone=self.mic_edit.text().strip() or "default",
            copy_to_clipboard=self.copy_check.isChecked(),
            auto_paste=self.paste_check.isChecked(),
            auto_type=self.type_check.isChecked(),
            add_trailing_space=self.space_check.isChecked(),
            notifications=self.notif_check.isChecked(),
            gnome_hotkey=self.gnome_hotkey_edit.text().strip(),
            evdev_hotkey=self.evdev_edit.text().strip(),
            beam_size=self.beam_spin.value(),
            temperature=self.temp_spin.value(),
            no_speech_threshold=self.nospeech_spin.value(),
            vad_filter=self.vad_check.isChecked(),
            initial_prompt=self.prompt_edit.text(),
        )

    def _save(self) -> None:
        self.cfg = self._collect()
        self._on_apply(self.cfg)
        self.set_status("Saved")

    # -- public (called from tray) -------------------------------------------

    def set_status(self, msg: str) -> None:
        self.status_label.setText(msg)

    def append_history(self, text: str) -> None:
        self.history_list.insertItem(0, text.strip())
        if self.history_list.count() > 100:
            self.history_list.takeItem(self.history_list.count() - 1)
