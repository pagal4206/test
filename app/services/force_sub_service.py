from html import escape
import threading
import time
from logging import Logger
from typing import Any, Optional

import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.constants import JOINED_STATUSES


class ForceSubService:
    def __init__(
        self,
        bot: telebot.TeleBot,
        warn_cooldown_seconds: int,
        logger: Logger,
    ) -> None:
        self.bot = bot
        self.warn_cooldown_seconds = warn_cooldown_seconds
        self.logger = logger
        self._warn_cache: dict[tuple[int, int], float] = {}
        self._warn_lock = threading.Lock()

    @staticmethod
    def normalize_chat_ref(chat_ref: Any) -> Any:
        if isinstance(chat_ref, str) and chat_ref.lstrip("-").isdigit():
            return int(chat_ref)
        return chat_ref

    @staticmethod
    def format_channel_ref(chat_ref: Optional[Any]) -> str:
        if not chat_ref:
            return "Not set"
        return str(chat_ref)

    def verify_channel_ref(self, channel_ref: str) -> Optional[str]:
        try:
            self.bot.get_chat(self.normalize_chat_ref(channel_ref))
        except ApiTelegramException as exc:
            self.logger.warning("Channel verify failed for %s: %s", channel_ref, exc)
            return str(exc)
        return None

    def is_joined(self, channel_ref: Any, user_id: int) -> bool:
        try:
            member = self.bot.get_chat_member(self.normalize_chat_ref(channel_ref), user_id)
        except ApiTelegramException as exc:
            self.logger.error(
                "get_chat_member failed for user %s and channel %s: %s",
                user_id,
                channel_ref,
                exc,
            )
            return True
        return member.status in JOINED_STATUSES

    def _should_warn(self, chat_id: int, user_id: int) -> bool:
        now = time.time()
        key = (chat_id, user_id)
        with self._warn_lock:
            last = self._warn_cache.get(key, 0)
            if now - last < self.warn_cooldown_seconds:
                return False
            self._warn_cache[key] = now
            return True

    def send_force_sub_warning(self, message: Message, join_link: Optional[str]) -> None:
        if not message.from_user:
            return

        if not self._should_warn(message.chat.id, message.from_user.id):
            return

        keyboard = None
        display_name = escape(message.from_user.first_name or "User")
        mention = f'<a href="tg://user?id={message.from_user.id}">{display_name}</a>'
        text = (
            f"{mention}, please join the required channel first.\n"
            "After joining, send your message again.\n\n"
            "कृपया पहले आवश्यक चैनल से जुड़ें।\n"
            "जुड़ने के बाद, अपना संदेश दोबारा भेजें।"
        )

        if join_link:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Join Channel", url=join_link))

        try:
            self.bot.send_message(message.chat.id, text, reply_markup=keyboard)
        except ApiTelegramException as exc:
            self.logger.warning("Failed to send warning in chat %s: %s", message.chat.id, exc)
