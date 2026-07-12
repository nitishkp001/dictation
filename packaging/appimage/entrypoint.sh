#!/bin/bash
# python-appimage entry point. Without this file the AppImage would launch the
# bare Python interpreter; instead we run the pip-installed `dictux` console
# script so CLI args (--toggle, --version, …) reach the app. The {{ }} tokens are
# substituted by python-appimage at build time.
{{ python-executable }} "${APPDIR}/opt/python{{ python-version }}/bin/dictux" "$@"
