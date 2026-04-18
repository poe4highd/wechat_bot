import sqlite3
import time
from pathlib import Path
from typing import Iterator
from contextlib import contextmanager
from loguru import logger
from storage.models import Message, SendLog

DEFAULT_DB = Path(__file__).parent.parent / "data" / "wechat_bot.db"


class Database:
    def __init__(self, path: Path = DEFAULT_DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Database ready: {path}")

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _create_tables(self):
        with self._tx() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id   TEXT NOT NULL,
                    chat_name TEXT NOT NULL,
                    sender    TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    ts        INTEGER NOT NULL,
                    is_group  INTEGER NOT NULL DEFAULT 0,
                    msg_hash  TEXT NOT NULL UNIQUE,
                    processed INTEGER NOT NULL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS send_log (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    target  TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts      INTEGER NOT NULL,
                    status  TEXT NOT NULL,
                    error   TEXT NOT NULL DEFAULT ''
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_hash ON messages(msg_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_ts   ON messages(ts)")

    # ── 消息 ──────────────────────────────────────────────────────────────

    def save_message(self, msg: Message) -> bool:
        try:
            with self._tx() as cur:
                cur.execute("""
                    INSERT OR IGNORE INTO messages
                        (chat_id, chat_name, sender, content, ts, is_group, msg_hash)
                    VALUES (?,?,?,?,?,?,?)
                """, (msg.chat_id, msg.chat_name, msg.sender, msg.content,
                      msg.ts, int(msg.is_group), msg.msg_hash))
            return True
        except Exception as e:
            logger.error(f"save_message error: {e}")
            return False

    def mark_processed(self, msg_hash: str):
        with self._tx() as cur:
            cur.execute(
                "UPDATE messages SET processed=1 WHERE msg_hash=?", (msg_hash,)
            )

    def recent_hashes(self, limit: int = 500) -> set[str]:
        cur = self._conn.execute(
            "SELECT msg_hash FROM messages ORDER BY ts DESC LIMIT ?", (limit,)
        )
        return {row["msg_hash"] for row in cur.fetchall()}

    def unprocessed(self, limit: int = 50) -> list[Message]:
        cur = self._conn.execute(
            "SELECT * FROM messages WHERE processed=0 ORDER BY ts LIMIT ?", (limit,)
        )
        return [_row_to_msg(r) for r in cur.fetchall()]

    # ── 发送日志 ──────────────────────────────────────────────────────────

    def log_send(self, target: str, content: str, status: str, error: str = ""):
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO send_log (target, content, ts, status, error) VALUES (?,?,?,?,?)",
                (target, content, int(time.time()), status, error),
            )

    def send_stats(self) -> dict:
        cur = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM send_log GROUP BY status"
        )
        return {row["status"]: row["cnt"] for row in cur.fetchall()}

    def message_stats(self) -> dict:
        cur = self._conn.execute("SELECT COUNT(*) as cnt FROM messages")
        total = cur.fetchone()["cnt"]
        cur = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE processed=0"
        )
        pending = cur.fetchone()["cnt"]
        return {"total": total, "pending": pending}


def _row_to_msg(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        chat_id=row["chat_id"],
        chat_name=row["chat_name"],
        sender=row["sender"],
        content=row["content"],
        ts=row["ts"],
        is_group=bool(row["is_group"]),
        msg_hash=row["msg_hash"],
        processed=bool(row["processed"]),
    )
