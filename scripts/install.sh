#!/bin/bash
# 一键安装：Python 依赖 + systemd 服务
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== WechatBot Install ==="

# Python 依赖
cd "$PROJECT_DIR"
if command -v pip &>/dev/null; then
    pip install -e .
else
    echo "ERROR: pip not found. Install Python 3.11+ first."
    exit 1
fi

# data 目录
mkdir -p "$PROJECT_DIR/data/logs"

# .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "Created .env from .env.example — fill in your API keys!"
fi

# systemd user service
mkdir -p "$HOME/.config/systemd/user"
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/wechat-bot.service" \
    > "$HOME/.config/systemd/user/wechat-bot.service"
systemctl --user daemon-reload
systemctl --user enable wechat-bot

echo ""
echo "Done! Next steps:"
echo "  1. Fill in $PROJECT_DIR/.env"
echo "  2. Build & install the APK: cd apk && ./gradlew assembleDebug"
echo "     then: make install-apk"
echo "  3. Start: make start"
echo "  4. Check: make health"
