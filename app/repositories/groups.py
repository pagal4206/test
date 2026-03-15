from datetime import datetime, timezone
from logging import Logger
from typing import Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from telebot.types import Chat

from app.constants import GROUP_TYPES
from app.models import ForceSubConfig


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class GroupRepository:
    def __init__(self, collection: Collection, logger: Logger) -> None:
        self.collection = collection
        self.logger = logger

    def upsert_group(self, chat: Chat) -> None:
        if chat.type not in GROUP_TYPES:
            return

        try:
            self.collection.update_one(
                {"group_id": chat.id},
                {
                    "$set": {
                        "group_id": chat.id,
                        "title": chat.title,
                        "username": chat.username,
                        "type": chat.type,
                        "active": True,
                        "updated_at": _now_utc(),
                    },
                    "$setOnInsert": {
                        "created_at": _now_utc(),
                        "force_sub": {
                            "enabled": False,
                            "channel_ref": None,
                            "join_link": None,
                            "updated_at": _now_utc(),
                            "updated_by": None,
                        },
                    },
                },
                upsert=True,
            )
        except PyMongoError as exc:
            self.logger.error("Failed to upsert group %s: %s", chat.id, exc)

    def get_force_sub(self, chat_id: int) -> ForceSubConfig:
        try:
            doc = self.collection.find_one(
                {"group_id": chat_id},
                {"_id": 0, "force_sub": 1},
            )
        except PyMongoError as exc:
            self.logger.error("Failed to load force_sub config for %s: %s", chat_id, exc)
            return ForceSubConfig()

        force_sub = (doc or {}).get("force_sub") or {}
        return ForceSubConfig(
            enabled=bool(force_sub.get("enabled", False)),
            channel_ref=force_sub.get("channel_ref"),
            join_link=force_sub.get("join_link"),
        )

    def update_force_sub(
        self,
        chat_id: int,
        updated_by: Optional[int],
        *,
        enabled: Optional[bool] = None,
        channel_ref: Optional[str] = None,
        join_link: Optional[str] = None,
        clear_channel: bool = False,
    ) -> None:
        updates: dict[str, object] = {
            "active": True,
            "updated_at": _now_utc(),
            "force_sub.updated_at": _now_utc(),
            "force_sub.updated_by": updated_by,
        }
        if enabled is not None:
            updates["force_sub.enabled"] = enabled

        if clear_channel:
            updates["force_sub.channel_ref"] = None
            updates["force_sub.join_link"] = None
        else:
            if channel_ref is not None:
                updates["force_sub.channel_ref"] = channel_ref
            if join_link is not None:
                updates["force_sub.join_link"] = join_link

        try:
            self.collection.update_one({"group_id": chat_id}, {"$set": updates})
        except PyMongoError as exc:
            self.logger.error("Failed to update force_sub for %s: %s", chat_id, exc)

    def mark_inactive(self, group_id: int) -> None:
        try:
            self.collection.update_one(
                {"group_id": group_id},
                {"$set": {"active": False, "updated_at": _now_utc()}},
            )
        except PyMongoError as exc:
            self.logger.warning("Failed to mark group %s inactive: %s", group_id, exc)

    def count_active(self) -> int:
        try:
            return self.collection.count_documents({"active": True})
        except PyMongoError as exc:
            self.logger.error("Failed to count active groups: %s", exc)
            return 0

    def list_active_ids(self) -> list[int]:
        try:
            docs = self.collection.find({"active": True}, {"_id": 0, "group_id": 1})
            return [int(doc["group_id"]) for doc in docs if "group_id" in doc]
        except PyMongoError as exc:
            self.logger.error("Failed to fetch active groups: %s", exc)
            return []

