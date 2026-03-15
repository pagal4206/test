from logging import Logger

import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from app.constants import GROUP_ADMIN_STATUSES, GROUP_TYPES


class AuthService:
    def __init__(self, bot: telebot.TeleBot, admin_ids: set[int], logger: Logger) -> None:
        self.bot = bot
        self.admin_ids = admin_ids
        self.logger = logger

    def is_bot_admin(self, user_id: int) -> bool:
        return bool(self.admin_ids) and user_id in self.admin_ids

    def ensure_bot_admin(self, message: Message) -> bool:
        if message.from_user and self.is_bot_admin(message.from_user.id):
            return True

        self.bot.reply_to(
            message,
            "This command is available only to bot admins.\n"
            "Set `ADMIN_IDS` in your `.env` file.",
        )
        return False

    def is_group_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            member = self.bot.get_chat_member(chat_id, user_id)
        except ApiTelegramException as exc:
            self.logger.warning(
                "Failed to check admin rights for %s in %s: %s",
                user_id,
                chat_id,
                exc,
            )
            return False
        return member.status in GROUP_ADMIN_STATUSES

    def ensure_group_admin(self, message: Message) -> bool:
        if message.chat.type not in GROUP_TYPES:
            self.bot.reply_to(message, "This command works only in groups.")
            return False

        if not message.from_user:
            return False

        if self.is_group_admin(message.chat.id, message.from_user.id):
            return True

        self.bot.reply_to(message, "Only group admins can use this command.")
        return False
