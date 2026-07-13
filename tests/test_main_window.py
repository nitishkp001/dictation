"""Main-window tests (headless Qt): history rendering, search, delete, drop."""

from __future__ import annotations

from dictux.config import Config
from dictux.history import Recording, RecordingStore


def _window(tmp_path, **cbs):
    from dictux.main_window import MainWindow

    store = RecordingStore(path=tmp_path / "h.json", audio_dir=tmp_path / "rec")
    defaults = dict(
        on_toggle=lambda: None,
        on_open_settings=lambda: None,
        on_transcribe_file=lambda p: None,
        on_retranscribe=lambda i: None,
    )
    defaults.update(cbs)
    return MainWindow(Config(), store, **defaults), store


def test_empty_state_then_populates(qapp, tmp_path):
    win, store = _window(tmp_path)
    assert not win._empty.isHidden()          # empty-state shown
    store.add(Recording(text="first note"))
    win.refresh()
    assert win._empty.isHidden()              # hidden once there are recordings


def test_search_filters_cards(qapp, tmp_path):
    win, store = _window(tmp_path)
    store.add(Recording(text="buy milk"))
    store.add(Recording(text="email Bob"))
    win.refresh()
    win.search.setText("milk")
    # One card + trailing stretch item.
    cards = [win._list_layout.itemAt(i).widget()
             for i in range(win._list_layout.count())
             if win._list_layout.itemAt(i).widget()]
    assert len(cards) == 1
    assert "milk" in cards[0].rec.text


def test_delete_removes_from_store(qapp, tmp_path):
    win, store = _window(tmp_path)
    rec = Recording(text="temp")
    store.add(rec)
    win.refresh()
    win._delete(rec)
    assert store.all() == []
    assert not win._empty.isHidden()          # empty-state returns


def test_drop_triggers_file_transcription(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    dropped = []
    win, _ = _window(tmp_path, on_transcribe_file=dropped.append)
    media = tmp_path / "clip.wav"
    media.write_bytes(b"fake")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(media))])
    event = QDropEvent(QPointF(1, 1), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    win.dropEvent(event)
    assert dropped == [str(media)]
