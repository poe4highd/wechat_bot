import asyncio
import json
from typing import Callable, Awaitable
import websockets
from websockets.exceptions import ConnectionClosed
from loguru import logger


MessageHandler = Callable[[dict], Awaitable[None]]


class WechatBridgeClient:
    """
    连接 WechatBridge APK 的 WebSocket 客户端。
    APK 在 Android 设备内监听 8765，通过 adb forward 映射到宿主机 localhost:8765。
    """

    def __init__(
        self,
        url: str = "ws://localhost:8765",
        on_message: MessageHandler | None = None,
        reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 60.0,
    ):
        self.url = url
        self._on_message = on_message
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._running = False
        self._ws = None

    def set_handler(self, handler: MessageHandler):
        self._on_message = handler

    async def start(self):
        self._running = True
        delay = self._reconnect_delay
        while self._running:
            try:
                logger.info(f"Connecting to WechatBridge at {self.url}")
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    delay = self._reconnect_delay  # 连接成功，重置退避
                    logger.info("WechatBridge connected")
                    async for raw in ws:
                        await self._dispatch(raw)
            except ConnectionClosed as e:
                logger.warning(f"WechatBridge connection closed: {e}")
            except OSError as e:
                logger.warning(f"WechatBridge connection failed: {e}")
            except Exception as e:
                logger.exception(f"WechatBridge unexpected error: {e}")
            finally:
                self._ws = None

            if not self._running:
                break
            logger.info(f"Reconnecting in {delay:.0f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_reconnect_delay)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _dispatch(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from bridge: {raw[:100]}")
            return
        if self._on_message:
            await self._on_message(data)

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed
