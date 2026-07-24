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

# 1b. Keep the bundle icon in sync with the repo icon (AppIcon.icns)
if [ -f "$SCRIPT_DIR/AppIcon.icns" ]; then
  mkdir -p "$SRC_APP/Contents/Resources"
  cp "$SCRIPT_DIR/AppIcon.icns" "$SRC_APP/Contents/Resources/AppIcon.icns"
fi

# 2. Copy bundle to /Applications (with a display name that has a space)
rm -rf "$DEST_APP"
cp -R "$SRC_APP" "$DEST_APP"

# 3. Remove quarantine + ad-hoc sign so Gatekeeper lets it run
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true
codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true

# 4. Force macOS to refresh the (aggressively cached) app icon
touch "$DEST_APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "$DEST_APP" 2>/dev/null || true
rm -rf "$HOME/Library/Caches/com.apple.iconservices.store" 2>/dev/null || true
killall Finder 2>/dev/null || true

# 5. Add to the Dock (persistent)
defaults write com.apple.dock persistent-apps -array-add \
  "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>${DEST_APP}</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
killall Dock 2>/dev/null || true

echo ""
echo "=== Done ==="
echo "  • App installed: $DEST_APP"
echo "  • New running icon applied (teal→indigo, biegacz + linia tempa)."
echo "  • Added to Dock (click the icon to launch)."
echo "  • First launch: if macOS blocks it, right-click the app > Open once."
echo "  • The app opens http://localhost:8502 in your browser."
echo "  • If the OLD icon still shows: log out/in, or run 'killall Dock Finder'."
