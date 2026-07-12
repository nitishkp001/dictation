"""Floating recording indicator — a frameless always-on-top mini recorder.

Shows a pulsing dot + animated waveform + elapsed timer while recording, and a
spinner while transcribing. Clicking it stops the current recording.

Wayland note: clients can't set their own top-level position under Wayland, so the
bottom-centre placement is honoured on X11 and left to the compositor on Wayland.
A pixel-anchored overlay would need the wlr-layer-shell protocol (future work).
"""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class _Waveform(QWidget):
    """A small procedurally-animated VU meter (we don't sample live levels)."""

    def __init__(self, bars: int = 5, parent: QWidget | None = None):
        super().__init__(parent)
        self._n = bars
        self._phase = 0.0
        self.setFixedSize(bars * 6 - 3, 20)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start(70)

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase += 0.35
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().highlight().color()
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        w, h = 3, self.height()
        for i in range(self._n):
            level = (math.sin(self._phase + i * 0.7) + 1) / 2  # 0..1
            bar_h = 4 + level * (h - 4)
            x = i * (w + 3)
            y = (h - bar_h) / 2
            p.drawRoundedRect(x, int(y), w, int(bar_h), 1.5, 1.5)


class IndicatorWindow(QWidget):
    def __init__(self, on_click: Callable[[], None] | None = None):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._on_click = on_click
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._pill = QFrame(self)
        self._pill.setObjectName("pill")
        self._pill.setStyleSheet(
            "#pill { background: palette(window); border: 1px solid palette(mid);"
            " border-radius: 18px; }"
        )
        row = QHBoxLayout(self._pill)
        row.setContentsMargins(16, 9, 16, 9)
        row.setSpacing(10)

        self._dot = QLabel()
        self._dot.setFixedSize(11, 11)
        self._dot.setStyleSheet("background: #e2504a; border-radius: 5px;")
        self._dot_effect = QGraphicsOpacityEffect(self._dot)
        self._dot.setGraphicsEffect(self._dot_effect)
        self._blink = QTimer(self)
        self._blink.timeout.connect(self._toggle_dot)
        self._dot_on = True

        self._wave = _Waveform()
        self._timer_label = QLabel("0:00")
        self._timer_label.setStyleSheet("font-family: monospace;")
        self._status = QLabel("")
        self._hint = QLabel("click to stop")
        self._hint.setStyleSheet("color: palette(mid);")

        for wdg in (self._dot, self._wave, self._status, self._timer_label, self._hint):
            row.addWidget(wdg)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._pill)

        self._elapsed = 0
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick_clock)

    # -- state --------------------------------------------------------------

    def show_recording(self) -> None:
        self._status.setText("")
        self._status.hide()
        self._dot.show()
        self._wave.show()
        self._timer_label.show()
        self._hint.show()
        self._elapsed = 0
        self._timer_label.setText("0:00")
        self._wave.start()
        self._blink.start(600)
        self._clock.start(1000)
        self._present()

    def show_transcribing(self) -> None:
        self._wave.stop()
        self._blink.stop()
        self._clock.stop()
        self._dot.hide()
        self._wave.hide()
        self._timer_label.hide()
        self._hint.hide()
        self._status.setText("Transcribing…")
        self._status.show()
        self._present()

    def hide_indicator(self) -> None:
        self._wave.stop()
        self._blink.stop()
        self._clock.stop()
        self.hide()

    # -- internals ----------------------------------------------------------

    def _present(self) -> None:
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self) -> None:
        screen = self.screen() or (self.window().screen() if self.window() else None)
        try:
            from PySide6.QtGui import QGuiApplication

            geo = (screen or QGuiApplication.primaryScreen()).availableGeometry()
            self.adjustSize()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 80
            self.move(x, y)
        except Exception:
            pass

    def _toggle_dot(self) -> None:
        self._dot_on = not self._dot_on
        self._dot_effect.setOpacity(1.0 if self._dot_on else 0.25)

    def _tick_clock(self) -> None:
        self._elapsed += 1
        self._timer_label.setText(f"{self._elapsed // 60}:{self._elapsed % 60:02d}")

    def mousePressEvent(self, _event) -> None:
        if self._on_click:
            self._on_click()

    def paintEvent(self, _event) -> None:
        # WA_TranslucentBackground needs an explicit clear for clean rounded edges.
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
