import asyncio
import smtplib
from email.message import EmailMessage
from loguru import logger
from config import loader


class SessionGuard:
    """
    心跳守护：定期检查 Waydroid + 微信 + WebSocket 连通性。
    检测到异常时触发告警，不自动重登（防止账号风险）。
    """

    def __init__(self, waydroid_manager, ws_client, interval: int = 30):
        self._wm = waydroid_manager
        self._ws = ws_client
        self._interval = interval
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            await asyncio.sleep(self._interval)
            await self._check()

    async def stop(self):
        self._running = False

    async def _check(self):
        if not self._wm.heartbeat_ok():
            logger.error("Heartbeat failed: Waydroid or WeChat is down, attempting restart...")
            ok = self._wm.full_startup()
            if not ok:
                await self._alert("Waydroid 重启失败，需要人工介入")

        if not self._ws.is_connected:
            logger.warning("WechatBridge WebSocket disconnected (will auto-reconnect)")

    async def _alert(self, msg: str):
        logger.error(f"ALERT: {msg}")
        cfg = loader.settings()
        email = loader.env("ALERT_EMAIL")
        if not email:
            return
        try:
            em = EmailMessage()
            em["Subject"] = f"[WechatBot] 告警: {msg[:50]}"
            em["From"] = loader.env("SMTP_USER")
            em["To"] = email
            em.set_content(msg)
            with smtplib.SMTP(loader.env("SMTP_HOST", "smtp.gmail.com"),
                              int(loader.env("SMTP_PORT", "587"))) as s:
                s.starttls()
                s.login(loader.env("SMTP_USER"), loader.env("SMTP_PASSWORD"))
                s.send_message(em)
        except Exception as e:
            logger.error(f"Alert email failed: {e}")
