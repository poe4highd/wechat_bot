import pytest
from unittest.mock import AsyncMock, MagicMock
from storage.models import Message
from router.message_router import MessageRouter, Rule
from router.handlers.keyword_handler import KeywordHandler
from router.handlers.echo_handler import EchoHandler


def make_msg(content: str, chat_name: str = "测试群") -> Message:
    return Message(
        chat_id="test", chat_name=chat_name, sender="张三",
        content=content, ts=1000, is_group=True, msg_hash="abc123"
    )


@pytest.mark.asyncio
async def test_keyword_handler_matches():
    handler = KeywordHandler([{"keywords": ["帮助"], "reply": "这是帮助信息"}])
    sender = MagicMock()
    reply = await handler.handle(make_msg("帮助一下"), sender)
    assert reply == "这是帮助信息"


@pytest.mark.asyncio
async def test_keyword_handler_no_match():
    handler = KeywordHandler([{"keywords": ["帮助"], "reply": "帮助信息"}])
    sender = MagicMock()
    reply = await handler.handle(make_msg("你好"), sender)
    assert reply is None


@pytest.mark.asyncio
async def test_echo_handler():
    handler = EchoHandler()
    sender = MagicMock()
    reply = await handler.handle(make_msg("hello"), sender)
    assert "hello" in reply


@pytest.mark.asyncio
async def test_router_dispatches_and_sends():
    sender = MagicMock()
    router = MessageRouter(sender)
    handler = AsyncMock(return_value="回复内容")
    rule_cfg = {"name": "test", "match": {"type": "keyword", "keywords": ["#test"]}}

    class MockHandler:
        async def handle(self, msg, s): return "回复内容"

    rule = Rule(rule_cfg, MockHandler())
    router.add_rule(rule)

    msg = make_msg("#test这里")
    await router.dispatch(msg)
    sender.send_to.assert_called_once_with("测试群", "回复内容")
