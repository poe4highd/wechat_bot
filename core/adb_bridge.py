import subprocess
import threading
from pathlib import Path
from loguru import logger


class ADBBridge:
    """ADB 操作封装，面向发送/控制场景（读消息由 Accessibility Service 负责）"""

    def __init__(self, host: str = "192.168.240.1", port: int = 5555):
        self.serial = f"{host}:{port}"
        self._lock = threading.Lock()  # 保证同一时刻只有一个 ADB UI 操作

    # ── 基础命令 ──────────────────────────────────────────────────────────

    def shell(self, *args, timeout: int = 10) -> str:
        cmd = ["adb", "-s", self.serial, "shell", *args]
        try:
            return subprocess.check_output(
                cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout
            ).strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB shell timeout: {args}")
            return ""
        except subprocess.CalledProcessError as e:
            logger.error(f"ADB shell error: {e}")
            return ""

    def push(self, local: str | Path, remote: str) -> bool:
        ret = subprocess.run(
            ["adb", "-s", self.serial, "push", str(local), remote],
            capture_output=True,
        )
        return ret.returncode == 0

    def forward(self, local_port: int, remote_port: int) -> bool:
        ret = subprocess.run(
            ["adb", "-s", self.serial, "forward",
             f"tcp:{local_port}", f"tcp:{remote_port}"],
            capture_output=True,
        )
        return ret.returncode == 0

    def screenshot(self, save_path: str | Path) -> bool:
        """截图保存到本地，供调试用"""
        remote = "/sdcard/screen_tmp.png"
        self.shell("screencap", "-p", remote)
        ret = subprocess.run(
            ["adb", "-s", self.serial, "pull", remote, str(save_path)],
            capture_output=True,
        )
        return ret.returncode == 0

    # ── 输入操作（发送消息专用，需持锁） ─────────────────────────────────

    def input_text(self, text: str):
        # adb shell input text 不支持中文，中文走 uiautomator2 set_text
        escaped = text.replace(" ", "%s").replace("'", "\\'")
        self.shell("input", "text", escaped)

    def input_tap(self, x: int, y: int):
        self.shell("input", "tap", str(x), str(y))

    def input_keyevent(self, keycode: int):
        self.shell("input", "keyevent", str(keycode))

    # ── 进程管理 ──────────────────────────────────────────────────────────

    def start_app(self, activity: str):
        self.shell("am", "start", "-n", activity)

    def stop_app(self, package: str):
        self.shell("am", "force-stop", package)

    def is_process_alive(self, package: str) -> bool:
        return bool(self.shell("pidof", package))

    # ── Accessibility Service 管理 ────────────────────────────────────────

    def enable_accessibility(self, service_component: str):
        """开启 Accessibility Service，安装 APK 后调用一次"""
        self.shell(
            "settings", "put", "secure",
            "enabled_accessibility_services", service_component,
        )
        self.shell(
            "settings", "put", "secure",
            "accessibility_enabled", "1",
        )
        logger.info(f"Accessibility enabled: {service_component}")

    def is_accessibility_enabled(self, service_component: str) -> bool:
        enabled = self.shell(
            "settings", "get", "secure", "enabled_accessibility_services"
        )
        return service_component in enabled

    # ── 系统设置 ──────────────────────────────────────────────────────────

    def keep_screen_on(self):
        self.shell("settings", "put", "system", "screen_off_timeout", "2147483647")
        self.shell("settings", "put", "global", "zen_mode", "1")

    @property
    def lock(self) -> threading.Lock:
        return self._lock
