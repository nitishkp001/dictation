# Dictux — Voice Dictation for Linux

[![CI](https://github.com/nitishkp001/dictux/actions/workflows/ci.yml/badge.svg)](https://github.com/nitishkp001/dictux/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Dictux** is a local, private **voice-to-text dictation app for Linux**. Press a
hotkey, speak, and your words are transcribed with [Whisper](https://github.com/openai/whisper)
and dropped into whatever app is focused — fully **offline**, nothing sent to the cloud.
Works on **Wayland and X11**.

A Linux **SuperWhisper alternative** — inspired by
[OpenSuperWhisper](https://github.com/starmel/OpenSuperWhisper) (macOS), built on
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), PipeWire and Qt.

> Keywords: linux dictation, voice to text, speech to text, whisper, offline dictation,
> wayland dictation, voice typing, superwhisper for linux.

---

## Features

- 🎙️ **Hotkey dictation** — press to start, press to stop; text appears where your cursor is
- 🧠 **Multiple Whisper models** — Tiny → Large-v3 / Large-v3-Turbo / Distil, downloaded on demand and cached
- 🌍 **Multilingual** with auto-detection (or pin a language)
- 📋 **Flexible output** — copy to clipboard, auto-paste, or type directly
- 🔔 Desktop notifications and a system-tray menu
- ⚙️ Tunable decoding — beam size, temperature, VAD, initial prompt
- 🐧 **Wayland-first** (also works on X11); no cloud, no account, fully offline

## Requirements

- Linux with **PipeWire** (`pw-record`) — standard on modern Ubuntu/Fedora
- Python 3.10+
- Optional: `wl-clipboard` (clipboard), `ydotool` or `wtype` (auto-paste/type on Wayland),
  `libnotify-bin` (notifications)

## Install

### AppImage — no Python needed (easiest)

Grab `Dictux-x86_64.AppImage` from the [latest release](https://github.com/nitishkp001/dictux/releases/latest),
then:

```bash
chmod +x Dictux-x86_64.AppImage
./Dictux-x86_64.AppImage
```

It bundles Python and all dependencies. You still need `pw-record` (PipeWire) for
recording, and optionally `wl-clipboard`/`ydotool` for clipboard/auto-paste — see
[Requirements](#requirements).

### One-liner (recommended)

```bash
git clone https://github.com/nitishkp001/dictux.git
cd dictux
./packaging/install.sh
```

This installs the app in an isolated environment via `pipx`, adds a desktop entry
and icon, and (on GNOME) binds **Super + \\** to toggle recording.

### Manual

```bash
pipx install git+https://github.com/nitishkp001/dictux.git
# or, from a checkout:
pip install --user .
```

Then launch it:

```bash
dictux                                  # starts the tray app
dictux --install-hotkey '<Super>backslash'   # GNOME: bind a shortcut
```

On non-GNOME desktops, bind `dictux --toggle` to a key in your desktop's
keyboard-shortcut settings.

## Usage

1. Launch `dictux` — a microphone icon appears in your system tray.
2. Press your hotkey (default **Super + \\**) → recording starts.
3. Speak, then press the hotkey again → it transcribes and copies/pastes the text.
4. Left-click the tray icon to toggle; right-click for the menu (model, settings, quit).

Command reference:

| Command | Action |
|---|---|
| `dictux` | Launch the tray app |
| `dictux --toggle` | Start/stop recording (bind this to a key) |
| `dictux --start` / `--stop` / `--cancel` | Explicit control |
| `dictux --settings` | Open settings |
| `dictux --status` | Is it running? |
| `dictux --install-hotkey [ACCEL]` | Register the GNOME shortcut |

## Models

The catalog mirrors the original OpenSuperWhisper line-up, running on
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2). Pick one
in **Settings → Model** (grouped, with a download button + progress bar and a link
to each model's Hugging Face page) or from the tray **Model** menu. Models are
cached under `~/.cache/huggingface`.

| Group | Models | Notes |
|---|---|---|
| **Turbo V3** | large / medium / small | Same `large-v3-turbo` download, quantized at load (float16 → int8). **Recommended.** |
| **Standard** | Tiny, Tiny (EN), Base, Small, Medium, Large v3 | Classic Whisper sizes, 75 MB → 3 GB |
| **Distil** | Distil Large v3 | Near large-v3 quality, ~2× faster (English) |
| **Fine-tuned** | Turbo V3 Hebrew | ivrit.ai Hebrew fine-tune; auto-sets language to Hebrew |

Selecting a Turbo tier just changes the `compute_type` (quantization); the three
share one download. `int8` runs comfortably on CPU — with an NVIDIA GPU set
**Device → cuda** in Settings for `float16`.

## Auto-paste / auto-type on Wayland

Wayland blocks synthetic keystrokes by default, so typing into other apps needs
[`ydotool`](https://github.com/ReimuNotMoe/ydotool):

```bash
sudo apt install ydotool
sudo usermod -aG input "$USER"     # log out/in afterwards
systemctl --user enable --now ydotool   # or run: ydotoold &
```

Then enable **Auto-paste** or **Type directly** in Settings. Without it, the text
is still copied to your clipboard — just paste with Ctrl+V.

## How it works

```
hotkey ──► dictux --toggle ──(unix socket)──► running app
                                                  │
                                 pw-record ──► WAV ─┘
                                                  │
                                    faster-whisper (offline)
                                                  │
                                 clipboard / ydotool / notify
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,hotkey]'
python -m dictux           # run from source
pytest -q                  # run the test suite
```

## License

MIT — see [LICENSE](LICENSE). Inspired by
[OpenSuperWhisper](https://github.com/starmel/OpenSuperWhisper).
