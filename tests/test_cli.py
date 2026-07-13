"""CLI argument-handling tests (no running instance required)."""

from __future__ import annotations

from dictux.cli import main


def test_file_rejects_missing_path(capsys):
    rc = main(["--file", "/no/such/file.wav"])
    assert rc == 1
    assert "Not a file" in capsys.readouterr().err


def test_file_rejects_directory(tmp_path, capsys):
    rc = main(["--file", str(tmp_path)])
    assert rc == 1
    assert "Not a file" in capsys.readouterr().err
