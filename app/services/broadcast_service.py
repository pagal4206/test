import time
from logging import Logger
from typing import Optional

import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from app.models import BroadcastPayload, BroadcastSummary
from app.repositories.groups import GroupRepository
from app.repositories.users import UserRepository


class BroadcastService:
    def __init__(
        self,
        bot: telebot.TeleBot,
        user_repo: UserRepository,
        group_repo: GroupRepository,
        logger: Logger,
    ) -> None:
        self.bot = bot
        self.user_repo = user_repo
        self.group_repo = group_repo
        self.logger = logger

    @staticmethod
    def build_payload(message: Message) -> Optional[BroadcastPayload]:
        if message.reply_to_message:
            return BroadcastPayload(
                kind="copy",
                source_chat_id=message.reply_to_message.chat.id,
                source_message_id=message.reply_to_message.message_id,
            )

        if message.text:
            parts = message.text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                return BroadcastPayload(kind="text", text=parts[1].strip())

        return None

    @staticmethod
    def _is_permanent_chat_error(exc: ApiTelegramException) -> bool:
        code = getattr(exc, "error_code", None)
        description = str(exc).lower()
        if code == 403:
            return True
        if code == 400 and any(
            text in description
            for text in (
                "chat not found",
                "user is deactivated",
                "bot was kicked",
                "have no rights to send",
                "group chat was upgraded",
            )
        ):
            return True
        return False

    def _send_payload(self, chat_id: int, payload: BroadcastPayload) -> None:
        if payload.kind == "text":
            self.bot.send_message(chat_id, payload.text or "", parse_mode=None)
            return

        if payload.kind == "copy":
            if payload.source_chat_id is None or payload.source_message_id is None:
                raise ValueError("Invalid copy payload")
            try:
                self.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=payload.source_chat_id,
                    message_id=payload.source_message_id,
                )
            except AttributeError:
                self.bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=payload.source_chat_id,
                    message_id=payload.source_message_id,
                )
            return

        raise ValueError(f"Unsupported payload kind: {payload.kind}")

    def broadcast(self, payload: BroadcastPayload) -> BroadcastSummary:
        user_ids = self.user_repo.list_active_ids()
        group_ids = self.group_repo.list_active_ids()

        sent_users = 0
        failed_users = 0
        sent_groups = 0
        failed_groups = 0

        for user_id in user_ids:
            try:
                self._send_payload(user_id, payload)
                sent_users += 1
            except ApiTelegramException as exc:
                failed_users += 1
                self.logger.warning("Broadcast failed for user %s: %s", user_id, exc)
                if self._is_permanent_chat_error(exc):
                    self.user_repo.mark_inactive(user_id)
            except Exception as exc:
                failed_users += 1
                self.logger.warning("Broadcast unexpected failure for user %s: %s", user_id, exc)
            time.sleep(0.04)

        for group_id in group_ids:
            try:
                self._send_payload(group_id, payload)
                sent_groups += 1
            except ApiTelegramException as exc:
                failed_groups += 1
                self.logger.warning("Broadcast failed for group %s: %s", group_id, exc)
                if self._is_permanent_chat_error(exc):
                    self.group_repo.mark_inactive(group_id)
            except Exception as exc:
                failed_groups += 1
                self.logger.warning("Broadcast unexpected failure for group %s: %s", group_id, exc)
            time.sleep(0.04)

        return BroadcastSummary(
            total_targets=len(user_ids) + len(group_ids),
            sent_users=sent_users,
            failed_users=failed_users,
            sent_groups=sent_groups,
            failed_groups=failed_groups,
        )

