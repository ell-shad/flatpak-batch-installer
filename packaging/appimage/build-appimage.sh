#!/usr/bin/env bash
# Build a portable AppImage of Flathub Catalog Installer.
#
# Run on the OLDEST distro you want to support (e.g. Ubuntu 22.04):
#   bash packaging/appimage/build-appimage.sh
# Output: Flathub-Catalog-Installer-<version>-<arch>.AppImage (repo root)
#
# What gets bundled: system Python + stdlib, _tkinter, Tcl/Tk libs and
# scripts, plus this app installed via pip. The host provides: FUSE
# (or use --appimage-extract), an X11/Wayland session, and the `flatpak`
# binary itself (the whole point of the app — it drives host flatpak).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_ID="io.github.flathub-catalog-installer"
APP_NAME="Flathub-Catalog-Installer"
WORK="$ROOT/appimage-build"
APPDIR="$WORK/AppDir"
ARCH="$(uname -m)"
PY="${PYTHON3:-python3}"   # override with PYTHON3=/usr/bin/python3 in CI
VERSION="$($PY -c 'from flathub_gui import __version__; print(__version__)' 2>/dev/null || echo dev)"
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
if "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m pip install --no-deps --target="$SITE" "$ROOT" 2>&1 | tail -2
else
  cp -a "$ROOT/flathub_gui" "$SITE/"
fi
"$PY" -c "import sys; sys.path.insert(0, '$SITE'); import flathub_gui; print('bundled', flathub_gui.__version__)"

# --- desktop integration ---------------------------------------------------
cp "$ROOT/packaging/desktop/$APP_ID.desktop" "$APPDIR/"
cp "$ROOT/assets/hicolor/256x256/apps/$APP_ID.png" "$APPDIR/$APP_ID.png"
cp "$ROOT/assets/hicolor/256x256/apps/$APP_ID.png" "$APPDIR/.DirIcon"
cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
APPDIR="\$(dirname "\$(readlink -f "\$0")")"
export PYTHONHOME="\$APPDIR/usr"
export PYTHONPATH="\$APPDIR/usr/lib/python3/dist-packages"
export TCL_LIBRARY="\$APPDIR/usr/share/$(basename "$TCL_DIR")"
export TK_LIBRARY="\$APPDIR/usr/share/$(basename "$TK_DIR")"
export LD_LIBRARY_PATH="\$APPDIR/usr/lib:\$LD_LIBRARY_PATH"
exec "\$APPDIR/usr/bin/$(basename "$PYBIN")" -m flathub_gui "\$@"
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
