"""GNOME keybinding list-parsing tests (pure string logic, no gsettings call)."""

from __future__ import annotations

from dictux import hotkey


def test_parse_empty_variants():
    assert hotkey._parse_str_list("@as []") == []
    assert hotkey._parse_str_list("[]") == []
    assert hotkey._parse_str_list("") == []


def test_parse_single_and_multiple():
    assert hotkey._parse_str_list("['/a/']") == ["/a/"]
    assert hotkey._parse_str_list("['/a/', '/b/']") == ["/a/", "/b/"]


def test_format_roundtrip():
    items = ["/org/x/", "/org/y/"]
    formatted = hotkey._format_str_list(items)
    assert hotkey._parse_str_list(formatted) == items


def test_format_empty():
    assert hotkey._format_str_list([]) == "[]"
