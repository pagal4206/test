import logging

import telebot

from app.config import load_settings
from app.context import AppContext
from app.database import MongoStore
from app.handlers import register_handlers
from app.logging_setup import configure_logging
from app.repositories.groups import GroupRepository
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.broadcast_service import BroadcastService
from app.services.force_sub_service import ForceSubService


def create_app() -> AppContext:
    settings = load_settings()
    configure_logging()
    logger = logging.getLogger("forcesub-bot")

    mongo_store = MongoStore(settings.mongo_uri, settings.mongo_db_name)
    mongo_store.connect()

    bot = telebot.TeleBot(settings.bot_token, parse_mode="HTML")
    bot_id = bot.get_me().id

    user_repo = UserRepository(mongo_store.users_collection, logger)
    group_repo = GroupRepository(mongo_store.groups_collection, logger)
    auth_service = AuthService(bot, settings.admin_ids, logger)
    force_sub_service = ForceSubService(bot, settings.warn_cooldown_seconds, logger)
    broadcast_service = BroadcastService(bot, user_repo, group_repo, logger)

    ctx = AppContext(
        settings=settings,
        bot=bot,
        bot_id=bot_id,
        logger=logger,
        mongo_store=mongo_store,
        user_repo=user_repo,
        group_repo=group_repo,
        auth_service=auth_service,
        force_sub_service=force_sub_service,
        broadcast_service=broadcast_service,
    )
    register_handlers(bot, ctx)
    return ctx

