from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from loguru import logger

DB_PATH = Path(__file__).parent.parent / "data" / "scheduler.db"


class TaskScheduler:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        jobstores = {
            "default": SQLAlchemyJobStore(url=f"sqlite:///{DB_PATH}")
        }
        executors = {"default": AsyncIOExecutor()}
        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone="Asia/Shanghai",
        )

    def start(self):
        self._scheduler.start()
        logger.info("Scheduler started")

    def shutdown(self):
        self._scheduler.shutdown(wait=False)

    def add_cron_job(self, func, cron_expr: str, job_id: str, **kwargs):
        """
        cron_expr: '0 8 * * *' 格式（分 时 日 月 周）
        kwargs: 传给 func 的关键字参数
        """
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        minute, hour, day, month, day_of_week = parts
        self._scheduler.add_job(
            func,
            trigger="cron",
            id=job_id,
            replace_existing=True,
            minute=minute, hour=hour,
            day=day, month=month, day_of_week=day_of_week,
            kwargs=kwargs,
        )
        logger.info(f"Cron job added: {job_id} [{cron_expr}]")

    def remove_job(self, job_id: str):
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception:
            logger.warning(f"Job not found: {job_id}")

    def list_jobs(self) -> list[dict]:
        return [
            {"id": j.id, "next_run": str(j.next_run_time)}
            for j in self._scheduler.get_jobs()
        ]
