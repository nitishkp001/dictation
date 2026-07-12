#!/usr/bin/env bash
# Install Dictation for the current user: pipx app + desktop entry + icon + hotkey.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="dictation"

echo "==> Installing Dictation from ${REPO_DIR}"

# 1. System dependencies (best effort; needs sudo).
if command -v apt >/dev/null 2>&1; then
  echo "==> Installing system packages (pipewire-utils, wl-clipboard, libnotify-bin)"
  sudo apt-get update -qq || true
  sudo apt-get install -y pipewire-utils wl-clipboard libnotify-bin ydotool || true
fi

# 2. Install the Python app in an isolated environment via pipx.
if ! command -v pipx >/dev/null 2>&1; then
  echo "==> Installing pipx"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
fi
echo "==> Installing the dictation package"
pipx install --force "${REPO_DIR}"

# 3. Desktop entry + icon.
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
install -Dm644 "${REPO_DIR}/packaging/dictation.desktop" \
  "${DATA_HOME}/applications/${APP_ID}.desktop"
install -Dm644 "${REPO_DIR}/dictation/resources/icon.svg" \
  "${DATA_HOME}/icons/hicolor/scalable/apps/${APP_ID}.svg"
gtk-update-icon-cache "${DATA_HOME}/icons/hicolor" 2>/dev/null || true
update-desktop-database "${DATA_HOME}/applications" 2>/dev/null || true

# 4. Register the GNOME keyboard shortcut (Super+\) if on GNOME.
if command -v gsettings >/dev/null 2>&1; then
  echo "==> Registering GNOME shortcut (Super+\\) -> dictation --toggle"
  "$HOME/.local/bin/dictation" --install-hotkey '<Super>backslash' || true
fi

cat <<'EOF'

==> Done!
   Launch it from your app grid ("Dictation") or run:  dictation
   Then press Super+\ (or whatever you bound) to start/stop recording.

   Optional, for auto-paste/auto-type on Wayland (ydotool):
     sudo usermod -aG input "$USER"      # then log out/in
     systemctl --user enable --now ydotool || ydotoold &
EOF
