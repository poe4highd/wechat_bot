import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path(__file__).parent.parent / "data" / "logs"


def setup_logger(dev: bool = False):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()

    level = "DEBUG" if dev else "INFO"
    logger.add(sys.stderr, level=level, colorize=True,
                format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")

    logger.add(
        LOG_DIR / "bot_{time:YYYY-MM-DD}.log",
        rotation="00:00", retention="14 days",
        level="INFO", encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{line} | {message}",
    )
    logger.add(
        LOG_DIR / "error.log",
        rotation="10 MB", retention="30 days",
        level="ERROR", encoding="utf-8",
    )
