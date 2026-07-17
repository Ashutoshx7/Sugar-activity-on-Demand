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
#   ./install.sh              install the desktop launcher
#   ./install.sh --ring       also register the studio in the Sugar
#                             activity ring (symlinks this checkout into
#                             ~/Activities via `setup.py dev`)
#   ./install.sh --uninstall  remove launcher, desktop entry, icon and
#                             the Sugar ring registration

set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ACTIVITIES_DIR="$HOME/Activities"

LAUNCHER="$BIN_DIR/sugar-aod-studio"
DESKTOP_FILE="$APPS_DIR/sugar-aod-studio.desktop"
ICON_FILE="$ICON_DIR/sugar-aod-studio.svg"
RING_LINK="$ACTIVITIES_DIR/SugarActivityStudio.activity"

check_deps() {
    if ! python3 -c "import gi, sugar3" 2>/dev/null; then
        echo "Missing system dependencies (PyGObject and/or the Sugar" >&2
        echo "toolkit).  On Debian/Ubuntu install them with:" >&2
        echo >&2
        echo "  sudo apt install python3-gi gir1.2-gtk-3.0 \\" >&2
        echo "      python3-sugar3 sugar-toolkit-gtk3" >&2
        exit 1
    fi
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$LAUNCHER" "$DESKTOP_FILE" "$ICON_FILE"
    # `setup.py dev` leaves a symlink to the checkout in ~/Activities.
    [ -L "$RING_LINK" ] && rm -f "$RING_LINK"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPS_DIR" 2>/dev/null || true
    fi
    echo "Removed sugar-aod-studio launcher, desktop entry, icon and"
    echo "the Sugar activity-ring registration."
    exit 0
fi

if [ "${1:-}" = "--ring" ]; then
    check_deps
    # `setup.py dev` (sugar3 bundlebuilder) symlinks this checkout into
    # ~/Activities/SugarActivityStudio.activity so the Sugar shell shows
    # it in the activity ring, running the live code from the repo.
    ( cd "$REPO_DIR" && python3 setup.py dev )
    echo
    echo "Registered in the Sugar activity ring:"
    echo "  $RING_LINK -> $REPO_DIR"
    echo "Open the Sugar shell and look for \"Sugar Activity Studio\"."
    exit 0
fi

check_deps

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
