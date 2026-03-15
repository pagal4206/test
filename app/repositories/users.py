from datetime import datetime, timezone
from logging import Logger

from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from telebot.types import User


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    def __init__(self, collection: Collection, logger: Logger) -> None:
        self.collection = collection
        self.logger = logger

    def upsert_private_user(self, user: User) -> None:
        if not user or user.is_bot:
            return

        try:
            self.collection.update_one(
                {"user_id": user.id},
                {
                    "$set": {
                        "user_id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                        "active": True,
                        "updated_at": _now_utc(),
                    },
                    "$setOnInsert": {"created_at": _now_utc()},
                },
                upsert=True,
            )
        except PyMongoError as exc:
            self.logger.error("Failed to upsert private user %s: %s", user.id, exc)

    def mark_inactive(self, user_id: int) -> None:
        try:
            self.collection.update_one(
                {"user_id": user_id},
                {"$set": {"active": False, "updated_at": _now_utc()}},
            )
        except PyMongoError as exc:
            self.logger.warning("Failed to mark user %s inactive: %s", user_id, exc)

    def count_active(self) -> int:
        try:
            return self.collection.count_documents({"active": True})
        except PyMongoError as exc:
            self.logger.error("Failed to count active users: %s", exc)
            return 0

    def list_active_ids(self) -> list[int]:
        try:
            docs = self.collection.find({"active": True}, {"_id": 0, "user_id": 1})
            return [int(doc["user_id"]) for doc in docs if "user_id" in doc]
        except PyMongoError as exc:
            self.logger.error("Failed to fetch active users: %s", exc)
            return []

