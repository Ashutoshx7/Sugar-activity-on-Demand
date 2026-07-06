#!/bin/sh
# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Install the Sugar Activity Studio launcher for the current user:
# puts `sugar-aod-studio` on PATH and adds an app-menu entry.  The
# studio itself keeps running from this checkout — there is nothing
# to build and no files are copied out of the repository except the
# icon and desktop entry.
#
#   ./install.sh              install
#   ./install.sh --uninstall  remove launcher, desktop entry and icon

set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

LAUNCHER="$BIN_DIR/sugar-aod-studio"
DESKTOP_FILE="$APPS_DIR/sugar-aod-studio.desktop"
ICON_FILE="$ICON_DIR/sugar-aod-studio.svg"

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$LAUNCHER" "$DESKTOP_FILE" "$ICON_FILE"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    echo "Removed sugar-aod-studio launcher, desktop entry and icon."
    exit 0
fi

if ! python3 -c "import gi, sugar3" 2>/dev/null; then
    echo "Missing system dependencies (PyGObject and/or the Sugar" >&2
    echo "toolkit).  On Debian/Ubuntu install them with:" >&2
    echo >&2
    echo "  sudo apt install python3-gi gir1.2-gtk-3.0 \\" >&2
    echo "      python3-sugar3 sugar-toolkit-gtk3" >&2
    exit 1
fi

mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"

ln -sf "$REPO_DIR/bin/sugar-aod-studio" "$LAUNCHER"
cp "$REPO_DIR/data/sugar-aod-studio.svg" "$ICON_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Sugar Activity Studio
Comment=Generate real Sugar learning activities from a plain-language idea
Exec=$LAUNCHER
Icon=sugar-aod-studio
Terminal=false
Categories=Education;GTK;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "Installed:"
echo "  command    $LAUNCHER -> $REPO_DIR/bin/sugar-aod-studio"
echo "  app menu   $DESKTOP_FILE"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Note: $BIN_DIR is not on your PATH; add it with:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac
