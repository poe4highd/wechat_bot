import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

CONFIG_DIR = Path(__file__).parent
ROOT_DIR = CONFIG_DIR.parent

load_dotenv(ROOT_DIR / ".env")


def _load(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return _load("settings.yaml")

def rules() -> list[dict]:
    return _load("rules.yaml").get("rules", [])

def schedule() -> list[dict]:
    return _load("schedule.yaml").get("tasks", [])

def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)
