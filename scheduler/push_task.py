from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from loguru import logger

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class PushTask:
    """定时推送任务：渲染模板 → 调用 WechatSender 发送到目标列表。"""

    def __init__(self, sender):
        self._sender = sender
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
        )

    async def execute(self, targets: list[dict], content: str = "", template: str = "", ctx: dict | None = None):
        """
        targets: [{"type": "group"|"contact", "name": "xxx"}, ...]
        content: 直接文本（与 template 二选一）
        template: Jinja2 模板文件名
        ctx: 模板渲染上下文
        """
        if template:
            text = self._render(template, ctx or {})
        else:
            text = content

        if not text:
            logger.warning("PushTask: empty content, skipped")
            return

        for target in targets:
            name = target.get("name", "")
            if not name:
                continue
            try:
                self._sender.send_to(name, text)
                logger.info(f"Push sent to [{name}]")
            except Exception as e:
                logger.error(f"Push failed to [{name}]: {e}")

    def _render(self, template_name: str, ctx: dict) -> str:
        try:
            tmpl = self._jinja.get_template(template_name)
            return tmpl.render(**ctx)
        except Exception as e:
            logger.error(f"Template render error [{template_name}]: {e}")
            return ""
