from storage.models import Message
from .base_handler import BaseHandler


class EchoHandler(BaseHandler):
    """调试用：原样回显消息内容。"""

    async def handle(self, msg: Message, sender) -> str | None:
        return f"[echo] {msg.content}"
