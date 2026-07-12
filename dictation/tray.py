"""System-tray application: menu, status icon, and Engine wiring.

Engine callbacks fire on worker threads, so we bounce them through Qt signals
(``_Bridge``) to run UI updates on the GUI thread.
"""

from __future__ import annotations

import sys
from importlib.resources import files

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME, ipc, models
from .config import Config
from .core import Engine, State
from .settings_window import SettingsWindow


def _icon(color_state: State | None = None) -> QIcon:
    svg_path = files("dictation.resources") / "icon.svg"
    pix = QPixmap(str(svg_path))
    return QIcon(pix)


class _Bridge(QObject):
    state_changed = Signal(object)
    result = Signal(str, str)
    error = Signal(str)
    status = Signal(str)
    invoke = Signal(str)  # IPC command marshalled to the GUI thread


class TrayApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setQuitOnLastWindowClosed(False)

        self.engine = Engine(cfg)
        self.bridge = _Bridge()
        self._wire_bridge()

        self.settings_window: SettingsWindow | None = None

        self.tray = QSystemTrayIcon(_icon(), parent=self.app)
        self.tray.setToolTip(f"{APP_NAME} — idle")
        self._build_menu()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        # IPC server: route commands onto the GUI thread.
        self.server = ipc.Server(self._handle_ipc)
        self.server.start()

        self.engine.preload_model()

    # -- bridge / signals -----------------------------------------------------

    def _wire_bridge(self) -> None:
        self.engine.on_state_change = lambda s: self.bridge.state_changed.emit(s)
        self.engine.on_result = lambda t, st: self.bridge.result.emit(t, st)
        self.engine.on_error = lambda m: self.bridge.error.emit(m)
        self.engine.on_status = lambda m: self.bridge.status.emit(m)

        self.bridge.state_changed.connect(self._on_state_changed)
        self.bridge.result.connect(self._on_result)
        self.bridge.error.connect(self._on_error)
        self.bridge.status.connect(self._on_status)
        self.bridge.invoke.connect(self._on_ipc_command)

    def _handle_ipc(self, command: str) -> str:
        command = command.strip()
        if command == "ping":
            return "pong"
        if command not in ipc.COMMANDS:
            return f"unknown command: {command}"
        # Marshal to GUI thread; reply immediately.
        self.bridge.invoke.emit(command)
        return "ok"

    def _on_ipc_command(self, command: str) -> None:
        if command == "toggle":
            self.engine.toggle()
        elif command == "start":
            self.engine.start()
        elif command == "stop":
            self.engine.stop()
        elif command == "cancel":
            self.engine.cancel()
        elif command == "settings":
            self.open_settings()
        elif command == "quit":
            self.quit()

    # -- menu -----------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = QMenu()

        self.action_toggle = QAction("Start recording", menu)
        self.action_toggle.triggered.connect(self.engine.toggle)
        menu.addAction(self.action_toggle)

        menu.addSeparator()

        self.model_menu = menu.addMenu("Model")
        self._model_group = QActionGroup(menu)
        self._model_group.setExclusive(True)
        self._rebuild_model_menu()

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.menu = menu
        self.tray.setContextMenu(menu)

    def _rebuild_model_menu(self) -> None:
        self.model_menu.clear()
        for m in models.MODELS:
            downloaded = "● " if models.is_downloaded(m.id) else "○ "
            act = QAction(f"{downloaded}{m.label}  ({m.size_mb} MB)", self.model_menu)
            act.setCheckable(True)
            act.setChecked(m.id == self.cfg.model)
            act.setData(m.id)
            act.triggered.connect(lambda _=False, mid=m.id: self._select_model(mid))
            self._model_group.addAction(act)
            self.model_menu.addAction(act)

    def _select_model(self, model_id: str) -> None:
        self.cfg.model = model_id
        self.cfg.save()
        self.engine.apply_config(self.cfg)
        self.engine.preload_model()
        self._rebuild_model_menu()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.engine.toggle()

    # -- state handlers -------------------------------------------------------

    def _on_state_changed(self, state: State) -> None:
        label = {
            State.IDLE: "Start recording",
            State.RECORDING: "Stop recording",
            State.TRANSCRIBING: "Transcribing…",
        }[state]
        self.action_toggle.setText(label)
        self.action_toggle.setEnabled(state != State.TRANSCRIBING)
        tip = {
            State.IDLE: "idle",
            State.RECORDING: "recording…",
            State.TRANSCRIBING: "transcribing…",
        }[state]
        self.tray.setToolTip(f"{APP_NAME} — {tip}")

    def _on_result(self, text: str, status: str) -> None:
        self.tray.setToolTip(f"{APP_NAME} — {status}")
        if self.settings_window is not None:
            self.settings_window.append_history(text)

    def _on_error(self, msg: str) -> None:
        self.tray.showMessage(APP_NAME, msg, QSystemTrayIcon.MessageIcon.Critical, 5000)

    def _on_status(self, msg: str) -> None:
        if self.settings_window is not None:
            self.settings_window.set_status(msg)

    # -- settings -------------------------------------------------------------

    def open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.cfg, on_apply=self._apply_settings)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _apply_settings(self, cfg: Config) -> None:
        self.cfg = cfg
        cfg.save()
        self.engine.apply_config(cfg)
        self._rebuild_model_menu()
        self.engine.preload_model()

    # -- lifecycle ------------------------------------------------------------

    def run(self) -> int:
        return self.app.exec()

    def quit(self) -> None:
        self.server.stop()
        self.app.quit()
