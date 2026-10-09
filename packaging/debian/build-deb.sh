#!/usr/bin/env bash
# Build a .deb for Debian/Ubuntu-family systems.
# No root and no debhelper needed: assembles the package tree and packs
# it with dpkg-deb. Run:  make deb   (or bash packaging/debian/build-deb.sh)
#
# Layout follows distro conventions where it matters:
#   /usr/lib/python3/dist-packages/flatpak_batch_installer  app (pure Python)
#   /usr/share/flatpak-batch-installer/deps                 ttkbootstrap wheel
#   /usr/bin/flatpak-batch-installer                        console script
#   /usr/share/{applications,icons,metainfo,doc}            integration
# Pillow/Tk/Flatpak come from the distro (see Depends) so the package
# stays "Architecture: all" and gets security updates with the system.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_ID="io.github.flatpak-batch-installer"
BIN="flatpak-batch-installer"
VERSION="$(python3 -c 'from flatpak_batch_installer import __version__; print(__version__)')"
DEB_VERSION="${VERSION}-1"
ARCH="all"  # pure Python app; Tk/Pillow/Flatpak come from distro Depends
WORK="$ROOT/deb-build"
STAGE="$WORK/root"
OUT="$ROOT/${BIN}_${DEB_VERSION}_${ARCH}.deb"

rm -rf "$WORK"
mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/usr/lib/python3/dist-packages" \
  "$STAGE/usr/share/$BIN/deps" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/metainfo" \
  "$STAGE/usr/share/doc/$BIN"

# --- app (pure Python, straight copy incl. data/icon.png) -------------------
cp -a "$ROOT/flatpak_batch_installer" "$STAGE/usr/lib/python3/dist-packages/"
find "$STAGE/usr/lib/python3/dist-packages" -type d -name __pycache__ \
  -prune -exec rm -rf {} + 2>/dev/null || true

# --- ttkbootstrap (pure-Python wheel, unpacked; Pillow comes from distro) --
if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "need pip to fetch ttkbootstrap (Debian/Ubuntu: python3-pip)"; exit 1
fi
mkdir -p "$WORK/wheels"
python3 -m pip download -q --no-deps --dest="$WORK/wheels" "ttkbootstrap>=1.10"
python3 - "$WORK/wheels" "$STAGE/usr/share/$BIN/deps" <<'EOF'
import glob
import os
import sys
import zipfile
wheels, dest = sys.argv[1], sys.argv[2]
found = sorted(glob.glob(os.path.join(wheels, "*.whl")))
assert found, "no wheels downloaded"
for whl in found:
    with zipfile.ZipFile(whl) as archive:
        archive.extractall(dest)
print("unpacked:", ", ".join(os.path.basename(w) for w in found))
EOF

# --- console script (script-dir on sys.path: no cwd shadowing) -------------
cat > "$STAGE/usr/bin/$BIN" <<EOF
#!/usr/bin/python3
"""Installed launcher for Flatpak Batch Installer (see flatpak-gui.py)."""
import os
import sys
sys.path.insert(0, os.environ.get(
    "FLATPAK_BATCH_INSTALLER_DEPS",
    "/usr/share/$BIN/deps"))
from flatpak_batch_installer.app import main
if __name__ == "__main__":
    raise SystemExit(main())
EOF
chmod 755 "$STAGE/usr/bin/$BIN"

# --- desktop integration ----------------------------------------------------
cp "$ROOT/packaging/desktop/$APP_ID.desktop" "$STAGE/usr/share/applications/"
cp "$ROOT/packaging/metainfo/$APP_ID.metainfo.xml" "$STAGE/usr/share/metainfo/"
for size in 16 32 48 64 128 256 512; do
  d="$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$d"
  cp "$ROOT/assets/hicolor/${size}x${size}/apps/$APP_ID.png" "$d/"
done
cp "$ROOT/LICENSE" "$STAGE/usr/share/doc/$BIN/LICENSE"
cat > "$STAGE/usr/share/doc/$BIN/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: $BIN
Upstream-Contact: Elshad Guliyev <ellshad.012@gmail.com>
Source: https://github.com/ell-shad/flatpak-batch-installer

Files: *
Copyright: 2026 Flatpak Batch Installer contributors
License: GPL-3.0-or-later
EOF
cp "$ROOT/CHANGELOG.md" "$STAGE/usr/share/doc/$BIN/changelog"
gzip -9 -n "$STAGE/usr/share/doc/$BIN/changelog"
{
  echo "$BIN ($DEB_VERSION) unstable; urgency=medium"
  echo
  echo "  * Upstream release $VERSION. See CHANGELOG.md for details."
  echo
  echo " -- Elshad Guliyev <ellshad.012@gmail.com>  $(date -R)"
} | gzip -9 -n > "$STAGE/usr/share/doc/$BIN/changelog.Debian.gz"
mkdir -p "$STAGE/usr/share/man/man1"
sed "s/@VERSION@/$VERSION/" "$ROOT/packaging/debian/$BIN.1" \
  | gzip -9 -n > "$STAGE/usr/share/man/man1/$BIN.1.gz"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $BIN
Version: $DEB_VERSION
Section: utils
Priority: optional
Architecture: all
Maintainer: Elshad Guliyev <ellshad.012@gmail.com>
Depends: python3 (>= 3.10), python3-tk, python3-pil, python3-pil.imagetk, flatpak
Description: Select many Flathub apps and install them with one command
 Browse the Flathub application catalog, tick multiple applications,
 and install all selected apps in a single Flatpak operation.
 Comes with a Tkinter GUI and a headless CLI mode.
EOF

# --- test the staged tree before packing ------------------------------------
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/usr/bin/$BIN"
STAGE_BIN="$STAGE/usr/bin/$BIN"
STAGE_OUT="$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$STAGE/usr/lib/python3/dist-packages" \
  FLATPAK_BATCH_INSTALLER_DEPS="$STAGE/usr/share/$BIN/deps" \
  "$STAGE_BIN" --version)"
echo "staged: $STAGE_OUT"
echo "$STAGE_OUT" | grep -q "$BIN $VERSION" || {
  echo "staged install did not report $BIN $VERSION"; exit 1; }

dpkg-deb --root-owner-group --build "$STAGE" "$OUT" >/dev/null
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
dpkg-deb --field "$OUT" Package Version Architecture Depends
if command -v lintian >/dev/null; then
  lintian "$OUT" || echo "(lintian reported issues above; build continues)"
else
  echo "(lintian not installed — skipping static checks)"
fi
