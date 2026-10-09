#!/usr/bin/env bash
# Build a portable AppImage of Flatpak Batch Installer.
#
# Run on the OLDEST distro you want to support (e.g. Ubuntu 22.04):
#   bash packaging/appimage/build-appimage.sh
# Output: Flatpak-Batch-Installer-<version>-<arch>.AppImage (repo root)
#
# What gets bundled: system Python + stdlib, _tkinter, Tcl/Tk libs and
# scripts, plus this app installed via pip. The host provides: FUSE
# (or use --appimage-extract), an X11/Wayland session, and the `flatpak`
# binary itself (the whole point of the app — it drives host flatpak).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_ID="io.github.flatpak-batch-installer"
APP_NAME="Flatpak-Batch-Installer"
WORK="$ROOT/appimage-build"
APPDIR="$WORK/AppDir"
ARCH="$(uname -m)"
PY="${PYTHON3:-python3}"   # override with PYTHON3=/usr/bin/python3 in CI
VERSION="$($PY -c 'from flatpak_batch_installer import __version__; print(__version__)' 2>/dev/null || echo dev)"
OUT="$ROOT/${APP_NAME}-${VERSION}-${ARCH}.AppImage"

command -v mksquashfs >/dev/null || { echo "need squashfs-tools (mksquashfs)"; exit 1; }
command -v "$PY" >/dev/null || { echo "need python3"; exit 1; }

PYVER="$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYBIN="$(readlink -f "$(command -v "$PY")")"
STDLIB="$($PY -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"
LIBDIR="$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
LDLIB="$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDLIBRARY"))')"
echo "host python: $PYBIN ($PYVER), stdlib $STDLIB"

TCL_DIR="$(echo /usr/share/tcltk/tcl* | tr ' ' '\n' | head -1)"
TK_DIR="$(echo /usr/share/tcltk/tk* | tr ' ' '\n' | head -1)"
[ -d "$TCL_DIR" ] && [ -d "$TK_DIR" ] || { echo "need Tcl/Tk script dirs"; exit 1; }
find_lib() {  # $1 = libtcl|libtk → first real path, fallback $2
  local found
  found="$(ldconfig -p 2>/dev/null | grep -o '/[^ ]*'"$1"'[0-9.]*\.so\(\.[0-9][0-9.]*\)\?' | head -n 1)"
  if [ -n "$found" ] && [ -e "$found" ]; then
    echo "$found"
  else
    echo "$2"
  fi
}
TCL_LIB="$(find_lib libtcl /usr/lib/x86_64-linux-gnu/libtcl8.6.so)"
TK_LIB="$(find_lib libtk /usr/lib/x86_64-linux-gnu/libtk8.6.so)"
[ -e "$TCL_LIB" ] || { echo "tcl lib not found: $TCL_LIB"; exit 1; }
[ -e "$TK_LIB" ] || { echo "tk lib not found: $TK_LIB"; exit 1; }
echo "tcl: $TCL_LIB ($TCL_DIR) / tk: $TK_LIB ($TK_DIR)"

rm -rf "$WORK"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share"

# --- python runtime ------------------------------------------------------
cp "$PYBIN" "$APPDIR/usr/bin/"
cp "$LIBDIR/$LDLIB" "$APPDIR/usr/lib/" 2>/dev/null || true
cp -a "$STDLIB" "$APPDIR/usr/lib/python$PYVER"
find "$APPDIR/usr/lib/python$PYVER" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$APPDIR/usr/lib/python$PYVER/test" "$APPDIR/usr/lib/python$PYVER/idlelib" 2>/dev/null || true

# --- tcl/tk ---------------------------------------------------------------
cp -L "$TCL_LIB" "$TK_LIB" "$APPDIR/usr/lib/"
cp -a "$TCL_DIR" "$TK_DIR" "$APPDIR/usr/share/"

# --- ldd closure of the GUI stack (minus host-provided base/X libs) -------
EXCLUDE='ld-linux|libc\.so|libm\.so|libdl\.so|libpthread\.so|librt\.so|libutil\.so|libresolv|libnsl|libfontconfig|libfreetype'
for obj in "$APPDIR/usr/bin/$(basename "$PYBIN")" "$APPDIR/usr/lib/$(basename "$TCL_LIB")" \
           "$APPDIR/usr/lib/$(basename "$TK_LIB")" \
           "$APPDIR/usr/lib/python$PYVER/lib-dynload/_tkinter"*.so; do
  [ -e "$obj" ] || continue
  while read -r lib; do
    [ -n "$lib" ] || continue
    base="$(basename "$lib")"
    echo "$base" | grep -Eq "$EXCLUDE" && continue
    [ -e "$APPDIR/usr/lib/$base" ] || cp -L "$lib" "$APPDIR/usr/lib/" 2>/dev/null || true
  done < <(ldd "$obj" 2>/dev/null | grep -o '/[^ ]*' || true)
done

# --- the app itself --------------------------------------------------------
SITE="$APPDIR/usr/lib/python3/dist-packages"
mkdir -p "$SITE"
PIP_OK=0
if "$PY" -m pip --version >/dev/null 2>&1; then
  # Distro pips can be ancient (Ubuntu 22.04 ships pip 22.0), and old pip
  # silently produces broken local-dir installs (UNKNOWN-0.0.0, no
  # modules). A modern pip is required for a working bundle.
  # Newer distros additionally gate pip behind PEP 668, hence the retry.
  PIP_FLAGS=""
  "$PY" -m pip install -q --upgrade pip 2>/dev/null || PIP_FLAGS="--break-system-packages"
  [ -n "$PIP_FLAGS" ] && "$PY" -m pip install -q --upgrade $PIP_FLAGS pip
  # with deps: bundles ttkbootstrap for the modern themes
  # shellcheck disable=SC2086
  "$PY" -m pip install $PIP_FLAGS --target="$SITE" "$ROOT" 2>&1 | tail -2
  PIP_OK=1
else
  cp -a "$ROOT/flatpak_batch_installer" "$SITE/"
  echo "NOTE: no pip — bundled without ttkbootstrap, built-in themes apply"
fi
# Verify the BUNDLE, not the source tree: a neutral cwd keeps sys.path[0]
# from masking a missing/broken bundled package (this exact hole once
# shipped an empty AppImage that still "passed" its checks).
VERIFY_DIR="$(mktemp -d)"
BUNDLED_PY="$APPDIR/usr/bin/$(basename "$PYBIN")"
run_bundled() {
  APPDIR="$APPDIR" PYTHONHOME="$APPDIR/usr" PYTHONPATH="$SITE" \
  TCL_LIBRARY="$APPDIR/usr/share/$(basename "$TCL_DIR")" \
  TK_LIBRARY="$APPDIR/usr/share/$(basename "$TK_DIR")" \
  LD_LIBRARY_PATH="$APPDIR/usr/lib:${LD_LIBRARY_PATH:-}" \
  "$BUNDLED_PY" "$@"
}
(cd "$VERIFY_DIR" && run_bundled -m flatpak_batch_installer --version)
(cd "$VERIFY_DIR" && run_bundled -c "import flatpak_batch_installer; print('bundle imports ok', flatpak_batch_installer.__version__)")
if [ "$PIP_OK" = 1 ]; then
  (cd "$VERIFY_DIR" && run_bundled -c "import ttkbootstrap; from PIL import ImageTk; print('bundle themes ok', ttkbootstrap.__version__)")
fi
rm -rf "$VERIFY_DIR"

# --- desktop integration ---------------------------------------------------
cp "$ROOT/packaging/desktop/$APP_ID.desktop" "$APPDIR/"
cp "$ROOT/assets/hicolor/256x256/apps/$APP_ID.png" "$APPDIR/$APP_ID.png"
cp "$ROOT/assets/hicolor/256x256/apps/$APP_ID.png" "$APPDIR/.DirIcon"
cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
APPDIR="\$(dirname "\$(readlink -f "\$0")")"
# Never resolve modules from the caller's cwd (a stray source checkout
# there would shadow the bundle, or worse).
cd "\$APPDIR" || exit 1
export PYTHONHOME="\$APPDIR/usr"
export PYTHONPATH="\$APPDIR/usr/lib/python3/dist-packages"
export TCL_LIBRARY="\$APPDIR/usr/share/$(basename "$TCL_DIR")"
export TK_LIBRARY="\$APPDIR/usr/share/$(basename "$TK_DIR")"
export LD_LIBRARY_PATH="\$APPDIR/usr/lib:\$LD_LIBRARY_PATH"
exec "\$APPDIR/usr/bin/$(basename "$PYBIN")" -m flatpak_batch_installer "\$@"
EOF
chmod +x "$APPDIR/AppRun"

# --- pack -------------------------------------------------------------------
TOOL="$WORK/appimagetool.AppImage"
if [ ! -x "$TOOL" ]; then
  URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  if command -v curl >/dev/null; then
    curl -L -o "$TOOL" "$URL"
  else
    wget -O "$TOOL" "$URL"
  fi
  chmod +x "$TOOL"
fi
if "$TOOL" --version >/dev/null 2>&1; then
  RUNNER="$TOOL"
else
  echo "no FUSE? extracting appimagetool…"
  (cd "$WORK" && "$TOOL" --appimage-extract >/dev/null)
  RUNNER="$WORK/squashfs-root/AppRun"
fi
ARCH="$ARCH" "$RUNNER" "$APPDIR" "$OUT"
ls -la "$OUT"
