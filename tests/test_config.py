"""Config persistence tests (no GUI / no model download)."""

from __future__ import annotations

import json

from dictux import config
from dictux.config import Config


def test_defaults_are_sane():
    cfg = Config()
    assert cfg.model
    assert cfg.compute_type in ("int8", "int8_float16", "float16", "float32")
    assert 1 <= cfg.beam_size <= 10
    assert 0.0 <= cfg.no_speech_threshold <= 1.0


def test_save_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)

    cfg = Config(model="small", beam_size=3, language="fr")
    cfg.save()
    assert path.exists()

    loaded = Config.load()
    assert loaded.model == "small"
    assert loaded.beam_size == 3
    assert loaded.language == "fr"


def test_unknown_keys_are_ignored(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    path.write_text(json.dumps({"model": "medium", "removed_option": 123}))

    loaded = Config.load()
    assert loaded.model == "medium"
    assert not hasattr(loaded, "removed_option")


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    path.write_text("{not valid json")

    loaded = Config.load()
    assert loaded.model == Config().model
