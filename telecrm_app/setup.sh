#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# TeleCRM Flutter App — Quick Setup Script
# ═══════════════════════════════════════════════════════════
set -e

CONSTANTS="lib/core/constants.dart"

echo ""
echo "╔═══════════════════════════════════════╗"
echo "║         TeleCRM Setup Wizard          ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# ── 1. Ask for server URL ────────────────────────────────
echo "Where is your Django backend running?"
echo "  [1] Android Emulator (http://10.0.2.2:8000)"
echo "  [2] Real Device - Local Wi-Fi (enter IP)"
echo "  [3] Production server (enter URL)"
read -p "Choose [1/2/3]: " choice

case $choice in
  1)
    SERVER_URL="http://10.0.2.2:8000/api"
    ;;
  2)
    read -p "Enter your machine's LAN IP (e.g. 192.168.1.100): " lan_ip
    SERVER_URL="http://${lan_ip}:8000/api"
    ;;
  3)
    read -p "Enter full API URL (e.g. https://mycrm.com/api): " prod_url
    SERVER_URL="$prod_url"
    ;;
  *)
    SERVER_URL="http://10.0.2.2:8000/api"
    ;;
esac

echo ""
echo "✅ Server URL: $SERVER_URL"

# ── 2. Patch constants.dart ──────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS sed
  sed -i '' "s|static const String baseUrl = '.*'|static const String baseUrl = '$SERVER_URL'|" "$CONSTANTS"
else
  # Linux sed
  sed -i "s|static const String baseUrl = '.*'|static const String baseUrl = '$SERVER_URL'|" "$CONSTANTS"
fi
echo "✅ Patched $CONSTANTS"

# ── 3. Create asset directories ──────────────────────────
mkdir -p assets/images assets/animations assets/icons
echo "✅ Asset directories ready"

# ── 4. flutter pub get ───────────────────────────────────
echo ""
echo "⏳ Running flutter pub get..."
flutter pub get
echo "✅ Dependencies installed"

# ── 5. Check for connected devices ───────────────────────
echo ""
echo "📱 Connected devices:"
flutter devices
echo ""

# ── 6. Offer to run ──────────────────────────────────────
read -p "Run the app now? [Y/n]: " run_now
if [[ "$run_now" != "n" && "$run_now" != "N" ]]; then
  echo ""
  echo "🚀 Launching TeleCRM..."
  flutter run
fi

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  Setup complete!  Happy calling 📞               ║"
echo "╚═══════════════════════════════════════════════════╝"
