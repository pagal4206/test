import telebot

from app.context import AppContext
from app.handlers.admin_handlers import register_admin_handlers
from app.handlers.group_handlers import register_group_handlers
from app.handlers.help_handlers import register_help_handlers
from app.handlers.member_update_handlers import register_member_update_handlers
from app.handlers.private_handlers import register_private_handlers


def register_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    register_help_handlers(bot, ctx)
    register_private_handlers(bot, ctx)
    register_admin_handlers(bot, ctx)
    register_group_handlers(bot, ctx)
    register_member_update_handlers(bot, ctx)
