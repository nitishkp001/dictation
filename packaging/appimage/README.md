# AppImage recipe

Builds a portable, self-contained `Dictux-x86_64.AppImage` (bundled Python + all
dependencies) via [python-appimage](https://github.com/niess/python-appimage).

Files here:

- `dictux.desktop` — desktop entry; `Exec=dictux` names the pip console script
  used as the AppImage entry point.
- `requirements.txt`, `dictux.png` — **generated at build time** (git-ignored) by
  `../build-appimage.sh` (the wheel path and the rasterized icon).

## Build

```bash
# from the repo root
bash packaging/build-appimage.sh        # -> dist/dictux-*.AppImage
```

Build on an old glibc (manylinux / Ubuntu 22.04) for the AppImage to run on older
distros — see `.github/workflows/appimage.yml`, which builds and attaches it to
every release. Local builds on a newer glibc only run on that glibc or newer.
