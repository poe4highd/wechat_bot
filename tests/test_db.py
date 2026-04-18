import pytest
from storage.models import Message
from storage.db import Database


def make_msg(hash_suffix: str = "x") -> Message:
    return Message(
        chat_id="c1", chat_name="群A", sender="李四",
        content="test", ts=9999, is_group=True,
        msg_hash=f"hash_{hash_suffix}"
    )


def test_save_and_dedup(tmp_db: Database):
    msg = make_msg("1")
    assert tmp_db.save_message(msg)
    # 重复插入应被忽略
    assert tmp_db.save_message(msg)
    stats = tmp_db.message_stats()
    assert stats["total"] == 1


def test_recent_hashes(tmp_db: Database):
    for i in range(5):
        tmp_db.save_message(make_msg(str(i)))
    hashes = tmp_db.recent_hashes(10)
    assert len(hashes) == 5


def test_mark_processed(tmp_db: Database):
    msg = make_msg("p")
    tmp_db.save_message(msg)
    tmp_db.mark_processed(msg.msg_hash)
    stats = tmp_db.message_stats()
    assert stats["pending"] == 0
