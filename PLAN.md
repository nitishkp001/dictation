# Dictux — Linux port of OpenSuperWhisper

## Goal
A packaged, installable Linux app: hotkey → record → local Whisper transcription
→ paste into the focused app. Multiple downloadable models, like the original.

## Feature mapping (macOS original → Linux)

| OpenSuperWhisper (macOS) | This project (Linux) | Module |
|---|---|---|
| Global hotkey / hold-to-record | IPC toggle bound via GNOME `gsettings`; optional evdev | `ipc.py`, `hotkey.py` |
| Mic capture (AVFoundation) | `pw-record` (PipeWire), ffmpeg fallback | `recorder.py` |
| whisper.cpp engine + models | faster-whisper (CTranslate2), HF model cache | `transcriber.py`, `models.py` |
| Auto copy / auto paste (AX API) | `wl-copy`/`xclip` + `ydotool`/`wtype`/`xdotool` | `output.py` |
| Menu-bar app + indicator | Qt `QSystemTrayIcon` + notifications | `tray.py`, `notifications.py` |
| Settings window | Qt settings window | `settings_window.py` |
| Language select / auto-detect | language dropdown, `language="auto"` | `settings_window.py` |
| Transcription tuning | beam/temp/VAD/prompt | `config.py`, `transcriber.py` |

## Architecture
- `core.Engine` — Qt-free state machine (IDLE→RECORDING→TRANSCRIBING), runs
  transcription on a worker thread, fires callbacks.
- `tray.TrayApp` — Qt UI; marshals Engine callbacks to the GUI thread via signals;
  hosts the IPC server so `dictux --toggle` controls the running instance.
- `cli.main` — dispatches subcommands or launches the app.

## Packaging
- `pyproject.toml` → `pipx install`, console script `dictux`.
- `packaging/install.sh` → deps + `.desktop` + icon + GNOME shortcut.
- MIT licensed; README with install/usage; push to GitHub.

## Status / TODO
- [x] Core modules, Qt tray, settings, CLI, packaging, docs
- [x] Verify end-to-end on this machine (record → transcribe)
- [x] Test suite (`tests/`) + GitHub Actions CI (lint, test, GUI import, build)
- [x] Release workflow (tag `v*` → build + GitHub Release; optional PyPI publish)
- [ ] Optional: AppImage/Flatpak packaging
- [ ] Optional: hold-to-record, mouse-button trigger, drag-drop file transcription

## Releasing
Tag and push: `git tag v0.1.0 && git push origin v0.1.0`. The release workflow
builds sdist+wheel and attaches them to a GitHub Release. To also publish to PyPI,
set repo variable `PUBLISH_PYPI=true` and configure a PyPI Trusted Publisher.
