#!/bin/bash
# Copyright (C) 2026 Sugar Labs
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build a portable, single-file AppImage of Sugar Activity Studio.
#
# Strategy: linuxdeploy + its GTK plugin seed the GTK stack; we then
# overlay the system CPython, gi, sugar3, the Rsvg/SugarExt typelibs and
# libsugarext.so, and the whole repo.  appimagetool seals it.
#
#   ./packaging/appimage/build-appimage.sh
#
# Output: dist/Sugar_Activity_Studio-x86_64.AppImage
#
# Needs network the first run (downloads the three AppImage tools into
# packaging/appimage/tools/, which is gitignored).

set -euo pipefail

HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
BUILD="$HERE/build"
APPDIR="$BUILD/AppDir"
TOOLS="$HERE/tools"
ARCH_LIB="x86_64-linux-gnu"
PYVER="3.12"
DP="/usr/lib/python3/dist-packages"
ODP="$APPDIR/usr/lib/python3/dist-packages"
OTL="$APPDIR/usr/lib/$ARCH_LIB/girepository-1.0"

# AppImage tools mount via FUSE by default; extracting is more robust
# inside containers/CI and still works with FUSE present.
export APPIMAGE_EXTRACT_AND_RUN=1
export DEPLOY_GTK_VERSION=3

log() { printf '\n\033[1;35m==>\033[0m %s\n' "$*"; }

# --- 0. Preconditions ------------------------------------------------------
log "Checking the system Python stack"
python3 - <<'PY'
import gi, sugar3, cairo, dbus, six  # noqa: F401
print("system stack OK")
PY

command -v glib-compile-schemas >/dev/null || {
    echo "glib-compile-schemas missing (install libglib2.0-bin)" >&2; exit 1; }

# --- 1. Download the tools (first run only) --------------------------------
mkdir -p "$TOOLS"
fetch() {  # url dest
    [ -x "$2" ] && return 0
    log "Downloading $(basename "$2")"
    if command -v wget >/dev/null; then wget -qO "$2" "$1"; else curl -fsSL -o "$2" "$1"; fi
    chmod +x "$2"
}
BASE_LD="https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous"
# The GTK plugin is a raw script on master, not a release asset.
URL_GTK="https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh"
BASE_AT="https://github.com/AppImage/appimagetool/releases/download/continuous"
fetch "$BASE_LD/linuxdeploy-x86_64.AppImage"        "$TOOLS/linuxdeploy-x86_64.AppImage"
fetch "$URL_GTK"                                    "$TOOLS/linuxdeploy-plugin-gtk.sh"
fetch "$BASE_AT/appimagetool-x86_64.AppImage"       "$TOOLS/appimagetool-x86_64.AppImage"
export PATH="$TOOLS:$PATH"   # linuxdeploy finds the gtk plugin on PATH

# --- 2. Fresh AppDir skeleton ---------------------------------------------
log "Preparing AppDir"
rm -rf "$BUILD"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib/$ARCH_LIB/girepository-1.0" \
         "$APPDIR/usr/lib/python$PYVER" \
         "$ODP" \
         "$APPDIR/usr/share/glib-2.0/schemas" \
         "$APPDIR/usr/share/sugar-activity-studio" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# --- 3. Desktop + icon (appimagetool needs them at the AppDir root) --------
cp "$HERE/sugar-activity-studio.desktop" "$APPDIR/"
cp "$REPO/data/sugar-aod-studio.svg" "$APPDIR/sugar-aod-studio.svg"
cp "$REPO/data/sugar-aod-studio.svg" \
   "$APPDIR/usr/share/icons/hicolor/scalable/apps/sugar-aod-studio.svg"

# --- 4. Seed the GTK stack + bundle the interpreter's ELF deps -------------
log "Running linuxdeploy with the GTK plugin"
"$TOOLS/linuxdeploy-x86_64.AppImage" \
    --appdir "$APPDIR" \
    --plugin gtk \
    --executable "/usr/bin/python$PYVER" \
    --icon-file "$APPDIR/sugar-aod-studio.svg" \
    --desktop-file "$APPDIR/sugar-activity-studio.desktop"
# linuxdeploy dropped python3.12 in usr/bin; our AppRun wants python3.
ln -sf "python$PYVER" "$APPDIR/usr/bin/python3"

# --- 5. Bundle the Python standard library (pure-python; not ELF-traced) ---
log "Bundling the Python $PYVER standard library"
cp -a "/usr/lib/python$PYVER/." "$APPDIR/usr/lib/python$PYVER/"
find "$APPDIR/usr/lib/python$PYVER" -type d -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$APPDIR/usr/lib/python$PYVER/test" \
       "$APPDIR/usr/lib/python$PYVER/idlelib" \
       "$APPDIR/usr/lib/python$PYVER/turtledemo"

# --- 6. Bundle only the dist-packages we need ------------------------------
log "Bundling gi, sugar3, cairo, dbus, six"
cp -a "$DP/gi" "$DP/sugar3" "$DP/cairo" "$DP/dbus" "$ODP/"
cp -a "$DP"/six.py "$ODP/" 2>/dev/null || true
cp -a "$DP"/_dbus_bindings*.so "$DP"/_dbus_glib_bindings*.so "$ODP/" 2>/dev/null || true
find "$ODP" -type d -name __pycache__ -prune -exec rm -rf {} +

# --- 7. Sugar-specific GI: typelibs + the companion C library --------------
log "Bundling Rsvg/SugarExt typelibs and libsugarext.so"
TL="/usr/lib/$ARCH_LIB/girepository-1.0"
cp -a "$TL/Rsvg-2.0.typelib" "$TL/SugarExt-1.0.typelib" "$OTL/"
for extra in Secret-1 TelepathyGLib-0.12 Soup-3.0; do
    [ -f "$TL/$extra.typelib" ] && cp -a "$TL/$extra.typelib" "$OTL/" || true
done
cp -a /usr/lib/$ARCH_LIB/libsugarext.so.0* "$APPDIR/usr/lib/$ARCH_LIB/"
# Pull libsugarext's own shared-lib deps into the bundle.
"$TOOLS/linuxdeploy-x86_64.AppImage" --appdir "$APPDIR" \
    -l "/usr/lib/$ARCH_LIB/libsugarext.so.0"

# --- 7b. The librsvg gdk-pixbuf loader (every Sugar/app icon is SVG) --------
log "Bundling the SVG pixbuf loader + librsvg"
PB="/usr/lib/$ARCH_LIB/gdk-pixbuf-2.0/2.10.0/loaders"
OPB="$APPDIR/usr/lib/$ARCH_LIB/gdk-pixbuf-2.0/2.10.0/loaders"
mkdir -p "$OPB"
cp -a "$PB/libpixbufloader-svg.so" "$OPB/"
"$TOOLS/linuxdeploy-x86_64.AppImage" --appdir "$APPDIR" \
    -l "$PB/libpixbufloader-svg.so"     # pulls librsvg-2.so into the bundle

# --- 7c. The Sugar icon theme (computer-xo + category/action glyphs) --------
log "Bundling the Sugar icon theme"
cp -a /usr/share/icons/sugar "$APPDIR/usr/share/icons/"

# --- 8. GSettings schemas (org.sugarlabs.font etc.) ------------------------
log "Bundling and compiling GSettings schemas"
cp /usr/share/glib-2.0/schemas/*.xml \
   "$APPDIR/usr/share/glib-2.0/schemas/" 2>/dev/null || true
glib-compile-schemas "$APPDIR/usr/share/glib-2.0/schemas/"

# --- 9. Regenerate a relocatable gdk-pixbuf loaders.cache ------------------
# Include the SVG loader just added, and make loader paths basenames so they
# resolve via GDK_PIXBUF_MODULEDIR (set by AppRun) at runtime, not the build
# machine's absolute paths.
log "Regenerating a relocatable gdk-pixbuf loaders.cache"
CACHE="$APPDIR/usr/lib/$ARCH_LIB/gdk-pixbuf-2.0/2.10.0/loaders.cache"
QUERY="$(command -v gdk-pixbuf-query-loaders || echo \
  /usr/lib/$ARCH_LIB/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders)"
GDK_PIXBUF_MODULEDIR="$OPB" "$QUERY" > "$CACHE"
# strip the absolute loaders-dir prefix -> just the .so basename
sed -i "s|\"$OPB/|\"|g" "$CACHE"

# --- 10. The app itself ----------------------------------------------------
log "Copying the studio into the bundle"
rsync -a --delete \
    --exclude '.git' --exclude 'tests' --exclude '__pycache__' \
    --exclude 'dist' --exclude '.pytest_cache' \
    --exclude 'packaging/appimage/build' --exclude 'packaging/appimage/tools' \
    "$REPO/" "$APPDIR/usr/share/sugar-activity-studio/"

# --- 11. Our AppRun (overrides whatever linuxdeploy generated) -------------
install -Dm755 "$HERE/AppRun" "$APPDIR/AppRun"

# --- 12. Seal it -----------------------------------------------------------
log "Packing the AppImage"
mkdir -p "$REPO/dist"
OUT="$REPO/dist/Sugar_Activity_Studio-x86_64.AppImage"
ARCH=x86_64 "$TOOLS/appimagetool-x86_64.AppImage" "$APPDIR" "$OUT"

log "Done: $OUT"
ls -lh "$OUT"
