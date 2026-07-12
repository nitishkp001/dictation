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


def test_install_drops_legacy_path(monkeypatch):
    legacy = hotkey._LEGACY_PATHS[0]
    monkeypatch.setattr(hotkey, "_gsettings",
                        lambda *a: hotkey._format_str_list([legacy, "/other/"]))
    calls = []
    monkeypatch.setattr(hotkey, "_gset", lambda *a: calls.append(a))

    hotkey.install_gnome_hotkey("<Super>backslash")

    list_sets = [a for a in calls
                 if a[:3] == ("set", hotkey._BASE, "custom-keybindings")]
    assert list_sets, "expected the keybindings list to be written"
    paths = hotkey._parse_str_list(list_sets[0][3])
    assert legacy not in paths          # stale pre-rename entry removed
    assert hotkey._PATH in paths        # current entry present
    assert "/other/" in paths           # unrelated entries preserved


def test_remove_drops_current_and_legacy(monkeypatch):
    legacy = hotkey._LEGACY_PATHS[0]
    monkeypatch.setattr(hotkey, "_gsettings",
                        lambda *a: hotkey._format_str_list([hotkey._PATH, legacy, "/keep/"]))
    calls = []
    monkeypatch.setattr(hotkey, "_gset", lambda *a: calls.append(a))

    hotkey.remove_gnome_hotkey()

    paths = hotkey._parse_str_list(calls[-1][3])
    assert paths == ["/keep/"]
