import threading
import time
import uiautomator2 as u2
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


# 微信 resource-id（WeChat 8.0.47-8.0.49，如版本升级需重新 dump）
_RES = {
    "search_bar": "com.tencent.mm:id/j8t",       # 主界面搜索入口
    "search_input": "com.tencent.mm:id/bho",      # 搜索框输入
    "chat_input": "com.tencent.mm:id/al_",        # 聊天输入框
    "send_btn": "com.tencent.mm:id/b7v",          # 发送按钮
    "back_btn": "com.tencent.mm:id/action_bar_back_button",
}


class WechatSender:
    """
    使用 uiautomator2 向微信联系人/群发送文本消息。
    读消息由 Accessibility Service 负责，本类仅负责发送。
    同一时刻只允许一个发送操作（内部互斥锁）。
    """

    def __init__(self, device_serial: str = "192.168.240.1:5555"):
        self._serial = device_serial
        self._d: u2.Device | None = None
        self._lock = threading.Lock()

    def connect(self):
        logger.info(f"Connecting uiautomator2 to {self._serial}")
        self._d = u2.connect(self._serial)
        logger.info("uiautomator2 connected")

    def disconnect(self):
        self._d = None

    @property
    def d(self) -> u2.Device:
        if self._d is None:
            self.connect()
        return self._d

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_to(self, target: str, text: str):
        """向指定联系人或群名发送消息，target 为微信昵称/群名。"""
        with self._lock:
            self._navigate_to_chat(target)
            self._type_and_send(text)
            self._back_to_main()
            logger.info(f"Sent to [{target}]: {text[:40]}")

    def _navigate_to_chat(self, target: str):
        d = self.d
        # 确保在主界面，点搜索
        if not d(resourceId=_RES["search_bar"]).exists(timeout=3):
            d.press("home")
            time.sleep(1)
            d(resourceId=_RES["search_bar"]).wait(timeout=5)

        d(resourceId=_RES["search_bar"]).click()
        time.sleep(0.5)

        search = d(resourceId=_RES["search_input"])
        search.wait(timeout=5)
        search.clear_text()
        search.set_text(target)
        time.sleep(1)

        # 点击第一个搜索结果
        result = d(text=target)
        if not result.exists(timeout=5):
            raise RuntimeError(f"Contact not found: {target}")
        result.click()
        time.sleep(1)

    def _type_and_send(self, text: str):
        d = self.d
        input_box = d(resourceId=_RES["chat_input"])
        input_box.wait(timeout=5)
        input_box.click()
        input_box.set_text(text)
        time.sleep(0.3)
        d(resourceId=_RES["send_btn"]).click()
        time.sleep(0.5)

    def _back_to_main(self):
        self.d.press("back")
        time.sleep(0.3)
        self.d.press("back")
        time.sleep(0.3)
