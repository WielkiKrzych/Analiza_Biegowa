#!/bin/bash
# build_biegowa_app.sh — install "Analiza Biegowa.app" to /Applications and add to Dock.
# Run this ON YOUR MAC:  bash ~/Documents/Analiza_Biegowa/build_biegowa_app.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_APP="$SCRIPT_DIR/Analiza_Biegowa.app"
DEST_APP="/Applications/Analiza Biegowa.app"

echo "=== Installing Analiza Biegowa.app ==="

# 1. Make sure the launcher scripts are executable
chmod 755 "$SCRIPT_DIR/launcher.sh"
chmod 755 "$SRC_APP/Contents/MacOS/launcher"

# 2. Copy bundle to /Applications (with a display name that has a space)
rm -rf "$DEST_APP"
cp -R "$SRC_APP" "$DEST_APP"

# 3. Remove quarantine + ad-hoc sign so Gatekeeper lets it run
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true
codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true

# 4. Refresh icon cache
touch "$DEST_APP"

# 5. Add to the Dock (persistent)
defaults write com.apple.dock persistent-apps -array-add \
  "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>${DEST_APP}</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
killall Dock 2>/dev/null || true

echo ""
echo "=== Done ==="
echo "  • App installed: $DEST_APP"
echo "  • Added to Dock (click the icon to launch)."
echo "  • First launch: if macOS blocks it, right-click the app > Open once."
echo "  • The app opens http://localhost:8502 in your browser."
