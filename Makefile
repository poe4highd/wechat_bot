.PHONY: start stop restart status logs install install-apk forward health dev

start:
	systemctl --user start wechat-bot

stop:
	systemctl --user stop wechat-bot

restart:
	systemctl --user restart wechat-bot

status:
	systemctl --user status wechat-bot
	@echo ""
	@python -m wechat_bot status

logs:
	journalctl --user -u wechat-bot -f

install:
	pip install -e .
	cp systemd/wechat-bot.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable wechat-bot

install-apk:
	adb install -r apk/app/build/outputs/apk/debug/app-debug.apk
	@bash scripts/setup_adb_forward.sh

forward:
	@bash scripts/setup_adb_forward.sh

health:
	@bash scripts/health_check.sh

dev:
	python -m wechat_bot --dev
