import asyncio
import sys
import uvicorn
from loguru import logger

from utils.logger import setup_logger
from config import loader
from core.waydroid_manager import WaydroidManager
from core.adb_bridge import ADBBridge
from core.ws_client import WechatBridgeClient
from core.wechat_sender import WechatSender
from listener.event_listener import EventListener
from router.message_router import MessageRouter, Rule
from router.handlers.echo_handler import EchoHandler
from router.handlers.keyword_handler import KeywordHandler
from router.handlers.llm_handler import LLMHandler
from scheduler.task_scheduler import TaskScheduler
from scheduler.push_task import PushTask
from storage.db import Database
from utils.session_guard import SessionGuard
import api.server as api_server


def main():
    dev = "--dev" in sys.argv
    setup_logger(dev)

    cfg = loader.settings()
    adb_host = cfg.get("adb", {}).get("host", "192.168.240.1")
    adb_port = cfg.get("adb", {}).get("port", 5555)
    ws_url = cfg.get("bridge", {}).get("ws_url", "ws://localhost:8765")
    ws_port = int(ws_url.split(":")[-1])

    # ── 环境启动 ──────────────────────────────────────────────────────────
    wm = WaydroidManager(adb_host, adb_port)
    if not wm.full_startup(ws_port):
        logger.error("Environment startup failed, exiting")
        sys.exit(1)

    # ── 核心组件 ──────────────────────────────────────────────────────────
    db = Database()
    sender = WechatSender(f"{adb_host}:{adb_port}")
    adb = ADBBridge(adb_host, adb_port)

    # 确保 Accessibility Service 已启用
    svc = cfg.get("wechat", {}).get("accessibility_service", "")
    if svc and not adb.is_accessibility_enabled(svc):
        adb.enable_accessibility(svc)

    # ── 路由规则装配 ──────────────────────────────────────────────────────
    router = MessageRouter(sender)
    for rule_cfg in loader.rules():
        handler_type = rule_cfg.get("handler", "keyword")
        if handler_type == "echo":
            handler = EchoHandler()
        elif handler_type == "llm":
            handler = LLMHandler(
                system_prompt=rule_cfg.get("system_prompt", "你是微信群助手，简洁友好地回复。")
            )
        else:
            handler = KeywordHandler([{
                "keywords": rule_cfg.get("match", {}).get("keywords", []),
                "reply": rule_cfg.get("reply", ""),
            }])
        router.add_rule(Rule(rule_cfg, handler))

    # ── 事件监听 ──────────────────────────────────────────────────────────
    event_listener = EventListener(db, router)
    ws_client = WechatBridgeClient(
        url=ws_url,
        on_message=event_listener.handle,
        reconnect_delay=cfg.get("bridge", {}).get("reconnect_delay", 2),
        max_reconnect_delay=cfg.get("bridge", {}).get("max_reconnect_delay", 60),
    )

    # ── 定时任务 ──────────────────────────────────────────────────────────
    scheduler = TaskScheduler()
    push_task = PushTask(sender)
    for task_cfg in loader.schedule():
        if not task_cfg.get("enabled", False):
            continue
        scheduler.add_cron_job(
            push_task.execute,
            cron_expr=task_cfg["cron"],
            job_id=task_cfg["name"],
            targets=task_cfg.get("targets", []),
            content=task_cfg.get("content", ""),
            template=task_cfg.get("content_template", ""),
        )

    # ── FastAPI ───────────────────────────────────────────────────────────
    api_cfg = cfg.get("api", {})
    api_server.init(sender, db, scheduler, ws_client)
    uvicorn_config = uvicorn.Config(
        app=api_server.app,
        host=api_cfg.get("host", "127.0.0.1"),
        port=api_cfg.get("port", 8000),
        log_level="warning",
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    # ── 心跳守护 ──────────────────────────────────────────────────────────
    guard = SessionGuard(wm, ws_client, cfg.get("heartbeat", {}).get("interval", 30))

    # ── 异步主循环 ────────────────────────────────────────────────────────
    async def run():
        scheduler.start()
        await asyncio.gather(
            ws_client.start(),
            guard.start(),
            uvicorn_server.serve(),
        )

    logger.info("WechatBot starting...")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
