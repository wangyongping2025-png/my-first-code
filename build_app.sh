#!/bin/bash
#
# Build QuickShot and assemble a proper .app bundle.
#
# A menu-bar (LSUIElement) app must live inside an .app bundle so macOS reads
# Info.plist. `swift build` alone produces a bare executable, so we wrap it here.
#
# Usage:   ./build_app.sh           # release build → ./QuickShot.app
#          open QuickShot.app        # run it
#
set -euo pipefail

APP_NAME="QuickShot"
BUILD_CONFIG="release"
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="$ROOT/$APP_NAME.app"

echo "==> Compiling ($BUILD_CONFIG)…"
swift build -c "$BUILD_CONFIG"

BIN_PATH="$(swift build -c "$BUILD_CONFIG" --show-bin-path)/$APP_NAME"

echo "==> Assembling $APP_NAME.app…"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

cp "$BIN_PATH" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
cp "$ROOT/Resources/Info.plist" "$APP_BUNDLE/Contents/Info.plist"

# Ad-hoc code signature. Required for stable Screen Recording / Accessibility
# permissions (the TCC database keys on the signature) and for SMAppService.
echo "==> Code signing (ad-hoc)…"
codesign --force --deep --sign - "$APP_BUNDLE"

echo "==> Done: $APP_BUNDLE"
echo "    Run with:  open \"$APP_BUNDLE\""
