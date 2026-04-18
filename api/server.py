from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="WechatBot API")

# 运行时注入
_sender = None
_db = None
_scheduler = None
_ws_client = None


def init(sender, db, scheduler, ws_client):
    global _sender, _db, _scheduler, _ws_client
    _sender = sender
    _db = db
    _scheduler = scheduler
    _ws_client = ws_client


class SendRequest(BaseModel):
    target: str
    content: str


@app.post("/send")
def send_message(req: SendRequest):
    if not _sender:
        raise HTTPException(503, "Sender not ready")
    try:
        _sender.send_to(req.target, req.content)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/status")
def status():
    return {
        "ws_connected": _ws_client.is_connected if _ws_client else False,
        "jobs": _scheduler.list_jobs() if _scheduler else [],
    }


@app.get("/stats")
def stats():
    if not _db:
        raise HTTPException(503, "DB not ready")
    return {
        "messages": _db.message_stats(),
        "sends": _db.send_stats(),
    }


@app.get("/jobs")
def list_jobs():
    if not _scheduler:
        raise HTTPException(503, "Scheduler not ready")
    return _scheduler.list_jobs()
