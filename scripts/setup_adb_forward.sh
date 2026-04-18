#!/bin/bash
# 建立 ADB port forward：localhost:8765 -> 设备:8765
set -e

ADB_HOST="${ADB_HOST:-192.168.240.1}"
ADB_PORT="${ADB_PORT:-5555}"
WS_PORT="${BRIDGE_WS_PORT:-8765}"
SERIAL="${ADB_HOST}:${ADB_PORT}"

echo "[setup_adb_forward] Connecting ADB to $SERIAL..."
adb connect "$SERIAL" 2>/dev/null || true

echo "[setup_adb_forward] Setting up port forward: localhost:$WS_PORT -> device:$WS_PORT"
adb -s "$SERIAL" forward "tcp:$WS_PORT" "tcp:$WS_PORT"

echo "[setup_adb_forward] Done."
