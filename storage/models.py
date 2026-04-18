from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    chat_id: str
    chat_name: str
    sender: str
    content: str
    ts: int
    is_group: bool
    msg_hash: str
    id: Optional[int] = field(default=None)
    processed: bool = False


@dataclass
class SendLog:
    target: str
    content: str
    ts: int
    status: str          # 'ok' | 'fail'
    error: str = ""
    id: Optional[int] = field(default=None)
