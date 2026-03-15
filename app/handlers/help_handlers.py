import telebot
from telebot.types import Message

from app.constants import GROUP_TYPES
from app.context import AppContext


def _build_help_text(is_group: bool) -> str:
    lines = [
        "<b>Help - ForceSub Bot</b>",
        "",
        "<b>General</b>",
        "/help - Show this help message",
        "/start - Start bot in dm",
        "",
        "<b>Group Admin Commands</b>",
        "/fsub &lt;channel_id/@username/link&gt; - Set force-sub channel",
        "/fsub &lt;channel_id/@username&gt; &lt;join_link&gt; - Set channel + custom join link",
        "/fsub off - Clear channel and disable force-sub",
        "/bot on - Enable force-sub in this group",
        "/bot off - Disable force-sub in this group",
        "/bot - Show current force-sub status",
    ]

    if not is_group:
        lines.append("")
        lines.append("Tip: Group commands work only inside a group where the bot is added.")

    return "\n".join(lines)


def register_help_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    @bot.message_handler(commands=["help"])
    def help_handler(message: Message) -> None:
        is_group = message.chat.type in GROUP_TYPES
        bot.reply_to(message, _build_help_text(is_group))
