#!/usr/bin/env bash
# Container entrypoint: bring up D-Bus + CUPS, register the printer queue, then run the bot.
set -e

PRINTER_NAME="${PRINTER_NAME:-HP_Color_LaserJet_Pro_MFP_M177fw}"
PRINTER_URI="${PRINTER_URI:-hp:/net/HP_Color_LaserJet_Pro_MFP_M177fw?ip=192.168.88.11}"
PRINTER_PPD="${PRINTER_PPD:-/app/printer-m177fw.ppd}"

# System D-Bus — the hpaio (HPLIP) SANE backend aborts without it.
dbus-uuidgen --ensure 2>/dev/null || true
mkdir -p /run/dbus
dbus-daemon --system --fork 2>/dev/null || true

# CUPS — local socket only (disable TCP 631) so it never clashes with the host under network_mode: host.
sed -i 's/^Listen localhost:631/#Listen localhost:631/' /etc/cups/cupsd.conf 2>/dev/null || true
mkdir -p /run/cups
cupsd
for i in $(seq 1 15); do lpstat -r >/dev/null 2>&1 && break; sleep 1; done

# Register the print queue (idempotent).
if [ -n "$PRINTER_NAME" ] && ! lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
  if [ -f "$PRINTER_PPD" ]; then
    if lpadmin -p "$PRINTER_NAME" -v "$PRINTER_URI" -P "$PRINTER_PPD" -E; then
      cupsenable "$PRINTER_NAME" 2>/dev/null || true
      cupsaccept "$PRINTER_NAME" 2>/dev/null || true
      echo "[entrypoint] printer queue '$PRINTER_NAME' ready"
    else
      echo "[entrypoint] WARNING: failed to register printer '$PRINTER_NAME'"
    fi
  else
    echo "[entrypoint] WARNING: PPD '$PRINTER_PPD' not found; printing disabled"
  fi
fi

# Optional: Uptime Kuma push heartbeat (set KUMA_PUSH_URL in .env to enable).
if [ -n "${KUMA_PUSH_URL:-}" ]; then
  ( while true; do curl -fsS --max-time 10 "$KUMA_PUSH_URL" >/dev/null 2>&1 || true; sleep "${KUMA_PUSH_INTERVAL:-30}"; done ) &
  echo "[entrypoint] Uptime Kuma heartbeat enabled (every ${KUMA_PUSH_INTERVAL:-30}s)"
fi

echo "[entrypoint] starting scan2telegram..."
exec python main.py
