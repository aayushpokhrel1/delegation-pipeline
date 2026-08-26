#!/usr/bin/env bash
# Remove the OmniRoute autostart entry (macOS launchd / Linux systemd --user).
# Run:  bash scripts/uninstall-autostart.sh
set -euo pipefail

LABEL="com.omniroute.gateway"
OS="$(uname -s)"

case "$OS" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    if [ -f "$PLIST" ]; then
      launchctl unload "$PLIST" 2>/dev/null || true
      rm -f "$PLIST"
      echo "Removed launchd agent: $PLIST"
    else
      echo "No launchd agent at $PLIST"
    fi
    ;;
  Linux)
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now omniroute.service 2>/dev/null || true
    fi
    UNIT="$HOME/.config/systemd/user/omniroute.service"
    if [ -f "$UNIT" ]; then
      rm -f "$UNIT"
      systemctl --user daemon-reload 2>/dev/null || true
      echo "Removed systemd user service: $UNIT"
    else
      echo "No systemd unit at $UNIT"
    fi
    ;;
  *)
    echo "Unsupported OS '$OS'. Use scripts/uninstall-autostart.ps1 on Windows." >&2
    exit 1
    ;;
esac
