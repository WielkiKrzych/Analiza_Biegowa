#!/bin/bash
# build_biegowa_app.sh — build a native, launchable "Analiza Biegowa.app" and add it to the Dock.
# Run this ON YOUR MAC:  bash ~/Documents/Analiza_Biegowa/build_biegowa_app.sh
#
# Uses osacompile to produce a proper AppleScript applet (real Mach-O executable),
# which launches reliably from Finder/Dock — unlike a hand-made shell-script bundle,
# which macOS Gatekeeper often refuses to open.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$SCRIPT_DIR/launcher.sh"
DEST_APP="/Applications/Analiza Biegowa.app"
ICON_PNG="$SCRIPT_DIR/icon.png"
ICON_ICNS="$SCRIPT_DIR/AppIcon.icns"

echo "=== Building Analiza Biegowa.app (osacompile) ==="

# 0. Sanity checks
command -v osacompile >/dev/null 2>&1 || { echo "FATAL: osacompile not found (macOS only)"; exit 1; }
chmod 755 "$LAUNCHER"

# 1. Build the applet from AppleScript that calls launcher.sh in the background
rm -rf "$DEST_APP"
osacompile -o "$DEST_APP" -e "do shell script \"'$LAUNCHER' > /tmp/analiza_biegowa_launch.log 2>&1 &\""

# 2. Build a REAL macOS .icns from icon.png (sips + iconutil) so Finder renders it.
#    A Pillow-made .icns is often incomplete and macOS falls back to the generic icon.
if [ -f "$ICON_PNG" ] && command -v iconutil >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"
  mkdir -p "$ICONSET"
  for sz in 16 32 128 256 512; do
    sips -z "$sz" "$sz"       "$ICON_PNG" --out "$ICONSET/icon_${sz}x${sz}.png"      >/dev/null 2>&1
    sips -z $((sz*2)) $((sz*2)) "$ICON_PNG" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$ICON_ICNS" 2>/dev/null || true
  rm -rf "$(dirname "$ICONSET")"
fi

# 2b. Install the icon into the applet (applets read Contents/Resources/applet.icns)
if [ -f "$ICON_ICNS" ]; then
  cp "$ICON_ICNS" "$DEST_APP/Contents/Resources/applet.icns"
fi

# 3. Set a friendly bundle identifier / name
/usr/libexec/PlistBuddy -c "Set :CFBundleName 'Analiza Biegowa'" "$DEST_APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.krzysztofkubicz.analizabiegowa" "$DEST_APP/Contents/Info.plist" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.krzysztofkubicz.analizabiegowa" "$DEST_APP/Contents/Info.plist" 2>/dev/null || true

# 4. De-quarantine + ad-hoc sign so it opens without warnings
xattr -dr com.apple.quarantine "$DEST_APP" 2>/dev/null || true
codesign --force --deep --sign - "$DEST_APP" 2>/dev/null || true

# 5. Refresh Launch Services + icon cache
touch "$DEST_APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "$DEST_APP" 2>/dev/null || true
rm -rf "$HOME/Library/Caches/com.apple.iconservices.store" 2>/dev/null || true
killall Finder 2>/dev/null || true

# 6. Add to the Dock (persistent)
defaults write com.apple.dock persistent-apps -array-add \
  "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>${DEST_APP}</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
killall Dock 2>/dev/null || true

echo ""
echo "=== Done ==="
echo "  • App built:   $DEST_APP"
echo "  • Icon:        running silhouette (teal→indigo)"
echo "  • Added to Dock — click to launch (opens http://localhost:8502)."
echo "  • First launch may take a few seconds while Streamlit boots."
echo "  • Troubleshooting: cat /tmp/analiza_biegowa_launch.log"
