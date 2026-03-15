from dataclasses import dataclass
from logging import Logger

import telebot

from app.config import Settings
from app.database import MongoStore
from app.repositories.groups import GroupRepository
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.broadcast_service import BroadcastService
from app.services.force_sub_service import ForceSubService


@dataclass
class AppContext:
    settings: Settings
    bot: telebot.TeleBot
    bot_id: int
    logger: Logger
    mongo_store: MongoStore
    user_repo: UserRepository
    group_repo: GroupRepository
    auth_service: AuthService
    force_sub_service: ForceSubService
    broadcast_service: BroadcastService

