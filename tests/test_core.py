"""Engine history/file/re-transcription tests (transcriber mocked, no models)."""

from __future__ import annotations

from dictux.config import Config
from dictux.core import Engine
from dictux.history import Recording, RecordingStore


class _FakeTranscriber:
    def __init__(self, text="hello there"):
        self.text = text

    def transcribe(self, path, cfg, progress=None):
        return self.text


def _engine(tmp_path, text="hello there"):
    store = RecordingStore(path=tmp_path / "h.json", audio_dir=tmp_path / "rec")
    eng = Engine(Config(), store=store)
    eng._transcriber = _FakeTranscriber(text)
    return eng, store


def test_save_recording_persists_audio(tmp_path):
    eng, store = _engine(tmp_path)
    seen = []
    eng.on_recording = seen.append
    wav = tmp_path / "clip.wav"
    wav.write_bytes(b"RIFFfake-audio")

    eng._save_recording("some text", 2.5, audio=wav)

    recs = store.all()
    assert len(recs) == 1
    assert recs[0].text == "some text"
    assert recs[0].audio_path and (tmp_path / "rec" / f"{recs[0].id}.wav").exists()
    assert seen and seen[0].text == "some text"


def test_file_worker_adds_history(tmp_path):
    eng, store = _engine(tmp_path, text="from a file")
    results = []
    eng.on_result = lambda t, s: results.append((t, s))
    media = tmp_path / "audio.mp3"
    media.write_bytes(b"fake")

    eng._file_worker(media)

    assert results and results[0][0] == "from a file"
    recs = store.all()
    assert recs[0].text == "from a file"
    assert recs[0].audio_path == str(media)   # references the source file


def test_retranscribe_updates_text(tmp_path):
    eng, store = _engine(tmp_path, text="updated transcription")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFFfake")
    rec = Recording(text="old", audio_path=str(audio))
    store.add(rec)
    got = []
    eng.on_retranscribed = lambda rid, txt: got.append((rid, txt))

    eng._retranscribe_worker(rec.id, audio)

    assert store.get(rec.id).text == "updated transcription"
    assert got == [(rec.id, "updated transcription")]
