"""RecordingStore tests (JSON persistence, search, limit, audio cleanup)."""

from __future__ import annotations

from dictux.history import Recording, RecordingStore


def _store(tmp_path, limit=100):
    return RecordingStore(
        path=tmp_path / "history.json",
        audio_dir=tmp_path / "recordings",
        limit=limit,
    )


def test_add_and_all(tmp_path):
    s = _store(tmp_path)
    s.add(Recording(text="hello world"))
    s.add(Recording(text="second"))
    items = s.all()
    assert [r.text for r in items] == ["second", "hello world"]  # newest first


def test_persistence_roundtrip(tmp_path):
    s = _store(tmp_path)
    s.add(Recording(text="persist me", model="base", duration=3.0))
    reloaded = _store(tmp_path)
    assert [r.text for r in reloaded.all()] == ["persist me"]
    assert reloaded.all()[0].model == "base"


def test_search_is_case_insensitive(tmp_path):
    s = _store(tmp_path)
    s.add(Recording(text="Buy Milk"))
    s.add(Recording(text="call Bob"))
    assert [r.text for r in s.search("milk")] == ["Buy Milk"]
    assert len(s.search("")) == 2


def test_delete_removes_audio(tmp_path):
    s = _store(tmp_path)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFfake")
    rec = Recording(text="x")
    rec.audio_path = s.persist_audio(audio, rec.id)
    s.add(rec)
    stored = tmp_path / "recordings" / f"{rec.id}.wav"
    assert stored.exists()
    s.delete(rec.id)
    assert not stored.exists()
    assert s.all() == []


def test_limit_evicts_oldest(tmp_path):
    s = _store(tmp_path, limit=2)
    s.add(Recording(text="one"))
    s.add(Recording(text="two"))
    s.add(Recording(text="three"))
    assert [r.text for r in s.all()] == ["three", "two"]


def test_update_text(tmp_path):
    s = _store(tmp_path)
    rec = Recording(text="old")
    s.add(rec)
    s.update_text(rec.id, "new")
    assert s.get(rec.id).text == "new"
