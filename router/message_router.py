import re
import time
from loguru import logger
from storage.models import Message
from router.handlers.base_handler import BaseHandler


class Rule:
    def __init__(self, cfg: dict, handler: BaseHandler):
        self.name = cfg.get("name", "unnamed")
        self.handler = handler
        self.cooldown = cfg.get("cooldown_seconds", 0)
        self.scope: list[str] = cfg.get("scope", [])  # 空列表=所有会话
        match_cfg = cfg.get("match", {})
        self._match_type = match_cfg.get("type", "keyword")
        self._keywords = [k.lower() for k in match_cfg.get("keywords", [])]
        self._pattern = re.compile(match_cfg.get("pattern", ""), re.IGNORECASE) if match_cfg.get("pattern") else None
        self._last_triggered: dict[str, float] = {}  # chat_id -> ts

    def matches(self, msg: Message) -> bool:
        if self.scope and msg.chat_name not in self.scope:
            return False
        if self._on_cooldown(msg.chat_id):
            return False
        text = msg.content.lower()
        if self._match_type == "keyword":
            return any(kw in text for kw in self._keywords)
        if self._match_type == "regex" and self._pattern:
            return bool(self._pattern.search(msg.content))
        if self._match_type == "all":
            return True
        return False

    def _on_cooldown(self, chat_id: str) -> bool:
        if not self.cooldown:
            return False
        last = self._last_triggered.get(chat_id, 0)
        return (time.time() - last) < self.cooldown

    def mark_triggered(self, chat_id: str):
        self._last_triggered[chat_id] = time.time()


class MessageRouter:
    def __init__(self, sender):
        self._rules: list[Rule] = []
        self._sender = sender

    def add_rule(self, rule: Rule):
        self._rules.append(rule)

    async def dispatch(self, msg: Message):
        for rule in self._rules:
            if not rule.matches(msg):
                continue
            reply = await rule.handler.handle(msg, self._sender)
            if reply:
                rule.mark_triggered(msg.chat_id)
                try:
                    self._sender.send_to(msg.chat_name, reply)
                    logger.info(f"Replied to [{msg.chat_name}] via rule '{rule.name}'")
                except Exception as e:
                    logger.error(f"Send failed: {e}")
            break  # 匹配第一条规则即停止
