"""Recording-indicator tests (headless Qt; skipped if Qt can't initialize)."""

from __future__ import annotations


def test_indicator_state_transitions(qapp):
    from dictux.indicator import IndicatorWindow

    clicks = []
    ind = IndicatorWindow(on_click=lambda: clicks.append(1))

    ind.show_recording()
    assert ind.isVisible()
    assert ind._clock.isActive()
    ind._tick_clock()
    ind._tick_clock()
    assert ind._timer_label.text() == "0:02"

    ind.show_transcribing()
    assert ind._status.text() == "Transcribing…"
    assert not ind._clock.isActive()          # timers stopped when transcribing

    ind.hide_indicator()
    assert not ind.isVisible()

    ind.mousePressEvent(None)                  # click stops recording
    assert clicks == [1]


def test_clock_formats_minutes(qapp):
    from dictux.indicator import IndicatorWindow

    ind = IndicatorWindow()
    ind._elapsed = 74
    ind._tick_clock()
    assert ind._timer_label.text() == "1:15"
