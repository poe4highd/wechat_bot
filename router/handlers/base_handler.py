from abc import ABC, abstractmethod
from storage.models import Message


class BaseHandler(ABC):
    @abstractmethod
    async def handle(self, msg: Message, sender) -> str | None:
        """处理消息，返回回复文本；返回 None 表示不回复。sender 为 WechatSender 实例。"""
