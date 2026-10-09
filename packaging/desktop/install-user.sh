#!/usr/bin/env bash
# Per-user install: desktop file + icon + launcher shim into ~/.local.
# No root needed. Run:  make install-user   (or bash packaging/desktop/install-user.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_ID="io.github.flathub-catalog-installer"
BIN_NAME="flathub-catalog-installer"

APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$APPS_DIR" "$ICON_DIR" "$BIN_DIR"

cp "$ROOT/packaging/desktop/$APP_ID.desktop" "$APPS_DIR/"
cp "$ROOT/assets/hicolor/256x256/apps/$APP_ID.png" "$ICON_DIR/"

# Shim: prefer an installed flathub-gui entry point, else run from this checkout.
cat > "$BIN_DIR/$BIN_NAME" <<EOF
#!/usr/bin/env bash
if command -v flathub-gui >/dev/null 2>&1; then
  exec flathub-gui "\$@"
else
  exec python3 "$ROOT/flathub-gui.py" "\$@"
fi
EOF
chmod +x "$BIN_DIR/$BIN_NAME"

update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "Installed for user $USER:"
echo "  desktop file: $APPS_DIR/$APP_ID.desktop"
echo "  icon:         $ICON_DIR/$APP_ID.png"
echo "  launcher:     $BIN_DIR/$BIN_NAME"
echo "Make sure ~/.local/bin is on your PATH."
