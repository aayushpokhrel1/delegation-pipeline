#!/usr/bin/env bash
# Install OmniRoute autostart at login: launchd on macOS, systemd --user on Linux.
# Run once:  bash scripts/install-autostart.sh
set -euo pipefail

LABEL="com.omniroute.gateway"
LOG="$HOME/.claude/omniroute.log"
mkdir -p "$HOME/.claude"

die() { echo "install-autostart: $*" >&2; exit 1; }

# Resolve how to launch omniroute (absolute paths, since login agents get a bare PATH).
if command -v omniroute >/dev/null 2>&1; then
  EXEC_ARGV="$(command -v omniroute)"
elif command -v npx >/dev/null 2>&1; then
  EXEC_ARGV="$(command -v npx) --yes omniroute"
else
  die "neither 'omniroute' nor 'npx' found on PATH. Install Node.js first."
fi
command -v node >/dev/null 2>&1 || die "node not found on PATH."
NODE_DIR="$(dirname "$(command -v node)")"
RUN_PATH="$NODE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

OS="$(uname -s)"
case "$OS" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    {
      echo '<?xml version="1.0" encoding="UTF-8"?>'
      echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
      echo '<plist version="1.0"><dict>'
      echo "  <key>Label</key><string>$LABEL</string>"
      echo '  <key>ProgramArguments</key><array>'
      for a in $EXEC_ARGV; do echo "    <string>$a</string>"; done
      echo '  </array>'
      echo '  <key>RunAtLoad</key><true/>'
      echo '  <key>KeepAlive</key><true/>'
      echo "  <key>StandardOutPath</key><string>$LOG</string>"
      echo "  <key>StandardErrorPath</key><string>$LOG</string>"
      echo '  <key>EnvironmentVariables</key><dict>'
      echo "    <key>PATH</key><string>$RUN_PATH</string>"
      echo '  </dict>'
      echo '</dict></plist>'
    } > "$PLIST"
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load -w "$PLIST"
    echo "Installed launchd agent -> $PLIST"
    echo "Manage: launchctl unload \"$PLIST\"  |  logs: $LOG"
    ;;

  Linux)
    command -v systemctl >/dev/null 2>&1 || die \
      "systemd not found. Fallback: add '@reboot bash $(pwd)/scripts/start-omniroute.sh' to your crontab."
    UNIT_DIR="$HOME/.config/systemd/user"
    UNIT="$UNIT_DIR/omniroute.service"
    mkdir -p "$UNIT_DIR"
    {
      echo '[Unit]'
      echo 'Description=OmniRoute AI gateway'
      echo 'After=network-online.target'
      echo 'Wants=network-online.target'
      echo
      echo '[Service]'
      echo 'Type=simple'
      echo "ExecStart=$EXEC_ARGV"
      echo 'Restart=on-failure'
      echo 'RestartSec=5'
      echo "Environment=PATH=$RUN_PATH"
      echo "StandardOutput=append:$LOG"
      echo "StandardError=append:$LOG"
      echo
      echo '[Install]'
      echo 'WantedBy=default.target'
    } > "$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --now omniroute.service
    echo "Installed systemd user service -> $UNIT"
    echo "To keep it running without an active login session, run once:"
    echo "  sudo loginctl enable-linger $USER"
    echo "Manage: systemctl --user status omniroute  |  logs: $LOG"
    ;;

  *)
    die "unsupported OS '$OS'. Use scripts/install-autostart.ps1 on Windows."
    ;;
esac
