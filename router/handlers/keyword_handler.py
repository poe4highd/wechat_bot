from storage.models import Message
from .base_handler import BaseHandler


class KeywordHandler(BaseHandler):
    """关键词 → 固定回复。rules 格式：[{"keywords": [...], "reply": "..."}]"""

    def __init__(self, rules: list[dict]):
        self._rules = rules

    async def handle(self, msg: Message, sender) -> str | None:
        text = msg.content.lower()
        for rule in self._rules:
            for kw in rule.get("keywords", []):
                if kw.lower() in text:
                    return rule["reply"]
        return None
