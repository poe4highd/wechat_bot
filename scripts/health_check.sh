#!/bin/bash
# 一键检查所有组件状态
ADB_HOST="${ADB_HOST:-192.168.240.1}"
ADB_PORT="${ADB_PORT:-5555}"
SERIAL="${ADB_HOST}:${ADB_PORT}"
WECHAT_PKG="com.tencent.mm"
BRIDGE_SVC="com.wechatbridge/.WechatAccessibilityService"
WS_PORT="${BRIDGE_WS_PORT:-8765}"

ok()  { echo "  [OK]  $1"; }
fail(){ echo "  [FAIL] $1"; }
warn(){ echo "  [WARN] $1"; }

echo "=== WechatBot Health Check ==="

# 1. Waydroid session
if waydroid status 2>/dev/null | grep -qi "RUNNING"; then
    ok "Waydroid session running"
else
    fail "Waydroid session NOT running"
fi

# 2. ADB
if adb -s "$SERIAL" shell echo ok 2>/dev/null | grep -q ok; then
    ok "ADB connected ($SERIAL)"
else
    fail "ADB NOT connected ($SERIAL)"
fi

# 3. 微信进程
if adb -s "$SERIAL" shell pidof "$WECHAT_PKG" 2>/dev/null | grep -q '[0-9]'; then
    ok "WeChat process running"
else
    fail "WeChat NOT running"
fi

# 4. Accessibility Service
ENABLED=$(adb -s "$SERIAL" shell settings get secure enabled_accessibility_services 2>/dev/null)
if echo "$ENABLED" | grep -q "com.wechatbridge"; then
    ok "WechatBridge Accessibility enabled"
else
    fail "WechatBridge Accessibility NOT enabled"
    echo "     Run: adb -s $SERIAL shell settings put secure enabled_accessibility_services $BRIDGE_SVC"
fi

# 5. Port forward
if adb -s "$SERIAL" forward --list 2>/dev/null | grep -q "tcp:$WS_PORT"; then
    ok "ADB port forward :$WS_PORT active"
else
    warn "ADB port forward :$WS_PORT not set, run: make forward"
fi

# 6. WebSocket 可达
if command -v wscat &>/dev/null; then
    if timeout 2 wscat -c "ws://localhost:$WS_PORT" 2>/dev/null; then
        ok "WebSocket ws://localhost:$WS_PORT reachable"
    else
        warn "WebSocket not reachable (APK may not be running)"
    fi
else
    warn "wscat not installed, skipping WebSocket check"
fi

# 7. Python Bot 进程
if systemctl --user is-active --quiet wechat-bot 2>/dev/null; then
    ok "wechat-bot systemd service active"
else
    warn "wechat-bot systemd service not active"
fi

echo "=============================="
