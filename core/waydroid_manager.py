import subprocess
import time
from loguru import logger


class WaydroidManager:
    WECHAT_PKG = "com.tencent.mm"
    WECHAT_ACTIVITY = "com.tencent.mm/.ui.LauncherUI"

    def __init__(self, adb_host: str = "192.168.240.1", adb_port: int = 5555):
        self.adb_host = adb_host
        self.adb_port = adb_port

    # ── Waydroid session ──────────────────────────────────────────────────

    def session_status(self) -> str:
        """返回 'running' / 'stopped' / 'unknown'"""
        try:
            out = subprocess.check_output(
                ["waydroid", "status"], text=True, stderr=subprocess.DEVNULL
            )
            if "RUNNING" in out.upper():
                return "running"
            return "stopped"
        except Exception:
            return "unknown"

    def start_session(self) -> bool:
        if self.session_status() == "running":
            logger.info("Waydroid session already running")
            return True
        logger.info("Starting Waydroid session...")
        ret = subprocess.run(["waydroid", "session", "start"], capture_output=True)
        if ret.returncode != 0:
            logger.error(f"waydroid session start failed: {ret.stderr.decode()}")
            return False
        # 等待 Android 完成启动
        for _ in range(30):
            time.sleep(2)
            if self._adb_alive():
                logger.info("Waydroid session started")
                return True
        logger.error("Waydroid session start timeout")
        return False

    def stop_session(self):
        logger.info("Stopping Waydroid session...")
        subprocess.run(["waydroid", "session", "stop"], capture_output=True)

    def restart_session(self) -> bool:
        self.stop_session()
        time.sleep(3)
        return self.start_session()

    # ── ADB 连通性 ────────────────────────────────────────────────────────

    def _adb_alive(self) -> bool:
        try:
            out = subprocess.check_output(
                ["adb", "-s", f"{self.adb_host}:{self.adb_port}", "shell", "echo", "ok"],
                timeout=5, text=True, stderr=subprocess.DEVNULL,
            )
            return out.strip() == "ok"
        except Exception:
            return False

    def ensure_adb_connected(self) -> bool:
        if self._adb_alive():
            return True
        logger.info(f"Connecting ADB to {self.adb_host}:{self.adb_port}...")
        ret = subprocess.run(
            ["adb", "connect", f"{self.adb_host}:{self.adb_port}"],
            capture_output=True, text=True,
        )
        connected = "connected" in ret.stdout.lower()
        if connected:
            logger.info("ADB connected")
        else:
            logger.error(f"ADB connect failed: {ret.stdout}")
        return connected

    # ── 微信进程 ──────────────────────────────────────────────────────────

    def is_wechat_running(self) -> bool:
        try:
            out = subprocess.check_output(
                ["adb", "-s", f"{self.adb_host}:{self.adb_port}",
                 "shell", "pidof", self.WECHAT_PKG],
                timeout=5, text=True, stderr=subprocess.DEVNULL,
            )
            return bool(out.strip())
        except Exception:
            return False

    def launch_wechat(self):
        logger.info("Launching WeChat...")
        subprocess.run([
            "adb", "-s", f"{self.adb_host}:{self.adb_port}",
            "shell", "am", "start", "-n", self.WECHAT_ACTIVITY,
        ], capture_output=True)
        time.sleep(5)

    def ensure_wechat_running(self):
        if not self.is_wechat_running():
            self.launch_wechat()

    # ── 屏幕保持唤醒 ──────────────────────────────────────────────────────

    def keep_screen_on(self):
        serial = f"{self.adb_host}:{self.adb_port}"
        subprocess.run([
            "adb", "-s", serial, "shell",
            "settings", "put", "system", "screen_off_timeout", "2147483647",
        ], capture_output=True)
        subprocess.run([
            "adb", "-s", serial, "shell",
            "settings", "put", "global", "zen_mode", "1",
        ], capture_output=True)
        logger.info("Screen keep-on + DND enabled")

    # ── ADB port forward（WebSocket 通道） ────────────────────────────────

    def setup_port_forward(self, local_port: int = 8765, remote_port: int = 8765):
        serial = f"{self.adb_host}:{self.adb_port}"
        ret = subprocess.run(
            ["adb", "-s", serial, "forward",
             f"tcp:{local_port}", f"tcp:{remote_port}"],
            capture_output=True, text=True,
        )
        if ret.returncode == 0:
            logger.info(f"ADB forward: localhost:{local_port} -> device:{remote_port}")
        else:
            logger.error(f"ADB forward failed: {ret.stderr}")

    # ── 全量启动检查 ──────────────────────────────────────────────────────

    def full_startup(self, ws_port: int = 8765) -> bool:
        """确保 Waydroid + ADB + 微信 + port forward 全部就绪"""
        if not self.start_session():
            return False
        if not self.ensure_adb_connected():
            return False
        self.keep_screen_on()
        self.ensure_wechat_running()
        self.setup_port_forward(ws_port, ws_port)
        return True

    def heartbeat_ok(self) -> bool:
        """心跳检测，供守护线程调用"""
        return self._adb_alive() and self.is_wechat_running()
