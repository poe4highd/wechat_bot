import hashlib
from loguru import logger
from storage.db import Database
from storage.models import Message


class EventListener:
    """
    接收 WechatBridge WebSocket 推入的消息事件，去重后入库，并分发给 Router。
    """

    def __init__(self, db: Database, router=None):
        self.db = db
        self.router = router  # 延迟注入，避免循环依赖
        self._seen: set[str] = set()  # 内存去重（重启后依赖 DB 补全）

    def set_router(self, router):
        self.router = router

    async def handle(self, event: dict):
        if event.get("type") != "message":
            logger.debug(f"Ignored event type: {event.get('type')}")
            return

        msg = self._parse(event)
        if msg is None:
            return

        if self._is_duplicate(msg):
            return

        self._seen.add(msg.msg_hash)
        self.db.save_message(msg)
        logger.info(f"[{msg.chat_name}] {msg.sender}: {msg.content[:60]}")

        if self.router:
            await self.router.dispatch(msg)

    def _parse(self, event: dict) -> "Message | None":
        content = (event.get("content") or "").strip()
        if not content:
            return None
        return Message(
            chat_id=event.get("chat_id", ""),
            chat_name=event.get("chat_name", ""),
            sender=event.get("sender", ""),
            content=content,
            ts=int(event.get("ts", 0)),
            is_group=bool(event.get("is_group", False)),
            msg_hash=_hash(event),
        )

    def _is_duplicate(self, msg: "Message") -> bool:
        if msg.msg_hash in self._seen:
            return True
        # 启动时从 DB 补全 seen 集合（仅查最近 500 条）
        if not self._seen:
            self._seen = self.db.recent_hashes(500)
        return msg.msg_hash in self._seen


def _hash(event: dict) -> str:
    raw = f"{event.get('chat_id')}{event.get('sender')}{event.get('content')}{event.get('ts', 0) // 60}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
