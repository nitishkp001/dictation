#!/usr/bin/env bash
# Build a portable Dictux AppImage using python-appimage.
#
# Produces a self-contained AppImage (bundled Python + all deps) under dist/.
# For a *portable* build (runs on older distros), run this on a manylinux base
# or an old Ubuntu (see .github/workflows/appimage.yml) — building on a very new
# glibc yields an AppImage that only runs on that glibc or newer.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECIPE_DIR="${REPO_DIR}/packaging/appimage"
PYVER="${PYVER:-3.11}"

cd "${REPO_DIR}"

echo "==> Building wheel"
python -m pip install --upgrade pip build python-appimage >/dev/null
rm -rf dist build ./*.egg-info
python -m build --wheel

WHEEL="$(ls -1 "${REPO_DIR}"/dist/dictux-*.whl | head -1)"
echo "==> Wheel: ${WHEEL}"

echo "==> Rasterizing icon -> dictux.png"
ICON_SVG="${REPO_DIR}/dictux/resources/icon.svg"
ICON_PNG="${RECIPE_DIR}/dictux.png"
if command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w 256 -h 256 "${ICON_SVG}" -o "${ICON_PNG}"
elif command -v inkscape >/dev/null 2>&1; then
  inkscape "${ICON_SVG}" --export-type=png -w 256 -h 256 -o "${ICON_PNG}"
elif python -c "import cairosvg" 2>/dev/null; then
  python -c "import cairosvg; cairosvg.svg2png(url='${ICON_SVG}', write_to='${ICON_PNG}', output_width=256, output_height=256)"
else
  echo "!! Need one of: rsvg-convert (librsvg2-bin), inkscape, or 'pip install cairosvg'" >&2
  exit 1
fi

echo "==> Writing recipe requirements.txt"
# Install the freshly built wheel (pip pulls its dependencies automatically).
printf '%s\n' "${WHEEL}" > "${RECIPE_DIR}/requirements.txt"

echo "==> Building AppImage (python-appimage, py${PYVER})"
python -m python_appimage build app -p "${PYVER}" "${RECIPE_DIR}"

# python-appimage drops the AppImage in the CWD.
mkdir -p "${REPO_DIR}/dist"
mv -f "${REPO_DIR}"/*.AppImage "${REPO_DIR}/dist/" 2>/dev/null || true
echo "==> Done:"
ls -1 "${REPO_DIR}"/dist/*.AppImage
