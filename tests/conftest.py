"""Shared test setup: force headless Qt so widget tests run without a display."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """A headless QApplication; skips the test if Qt can't initialize."""
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PySide6 unavailable: {e}")
    try:
        app = QApplication.instance() or QApplication([])
    except Exception as e:  # noqa: BLE001 - missing GL/EGL libs on some CI images
        pytest.skip(f"Qt platform unavailable: {e}")
    return app
