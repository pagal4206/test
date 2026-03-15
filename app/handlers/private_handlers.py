import telebot
from telebot.types import Message

from app.context import AppContext


def register_private_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    @bot.message_handler(commands=["start"])
    def start_handler(message: Message) -> None:
        if message.chat.type != "private":
            return

        if message.from_user:
            ctx.user_repo.upsert_private_user(message.from_user)

        bot.reply_to(
            message,
            "Welcome to ForceSub Bot.\n"
            "Use /help to see available commands.",
        )
