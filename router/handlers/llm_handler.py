import os
import httpx
from loguru import logger
from storage.models import Message
from .base_handler import BaseHandler


class LLMHandler(BaseHandler):
    """调用 Claude API 生成回复。"""

    def __init__(
        self,
        system_prompt: str = "你是一个微信群助手，简洁友好地回复用户消息。",
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 512,
    ):
        self._system = system_prompt
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    async def handle(self, msg: Message, sender) -> str | None:
        if not self._api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "max_tokens": self._max_tokens,
                        "system": self._system,
                        "messages": [{"role": "user", "content": msg.content}],
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"].strip()
        except Exception as e:
            logger.error(f"LLMHandler error: {e}")
            return None
