import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    warn_cooldown_seconds: int
    mongo_uri: str
    mongo_db_name: str
    admin_ids: set[int]


def _parse_admin_ids(raw_value: str) -> set[int]:
    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        cleaned = item.strip()
        if cleaned and cleaned.lstrip("-").isdigit():
            admin_ids.add(int(cleaned))
    return admin_ids


def _safe_int(raw_value: str, fallback: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return fallback


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017").strip()
    mongo_db_name = os.getenv("MONGO_DB_NAME", "forcesub_bot").strip()
    warn_cooldown_seconds = _safe_int(os.getenv("WARN_COOLDOWN_SECONDS", "600"), 600)
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", "").strip())

    if not bot_token:
        raise ValueError("BOT_TOKEN missing. Add it in .env")

    if not mongo_uri:
        raise ValueError("MONGO_URI missing. Add it in .env")

    return Settings(
        bot_token=bot_token,
        warn_cooldown_seconds=warn_cooldown_seconds,
        mongo_uri=mongo_uri,
        mongo_db_name=mongo_db_name,
        admin_ids=admin_ids,
    )
