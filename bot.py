import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import telebot
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from telebot.apihelper import ApiTelegramException
from telebot.types import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WARN_COOLDOWN_SECONDS = int(os.getenv("WARN_COOLDOWN_SECONDS", ""))
MONGO_URI = os.getenv("MONGO_URI", "").strip()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = {
    int(item.strip())
    for item in ADMIN_IDS_RAW.split(",")
    if item.strip() and item.strip().lstrip("-").isdigit()
}

GROUP_TYPES = {"group", "supergroup"}
JOINED_STATUSES = {"member", "administrator", "creator", "restricted"}
CHANNEL_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing. Add it in .env")

if not MONGO_URI:
    raise ValueError("MONGO_URI missing. Add it in .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forcesub-bot")

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
try:
    mongo_client.admin.command("ping")
except PyMongoError as exc:
    raise RuntimeError(f"MongoDB connection failed: {exc}") from exc

db = mongo_client[MONGO_DB_NAME]
users_collection: Collection = db["users"]
groups_collection: Collection = db["groups"]
users_collection.create_index("user_id", unique=True)
groups_collection.create_index("group_id", unique=True)
users_collection.create_index("active")
groups_collection.create_index("active")
groups_collection.create_index("force_sub.enabled")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
BOT_ID = bot.get_me().id
_warn_cache: dict[tuple[int, int], float] = {}
_warn_lock = threading.Lock()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_chat_ref(chat_ref: Any) -> Any:
    if isinstance(chat_ref, str) and chat_ref.lstrip("-").isdigit():
        return int(chat_ref)
    return chat_ref


def format_channel_ref(chat_ref: Optional[Any]) -> str:
    if not chat_ref:
        return "Not set"
    return str(chat_ref)


def is_admin(user_id: int) -> bool:
    return bool(ADMIN_IDS) and user_id in ADMIN_IDS


def ensure_admin(message: Message) -> bool:
    if message.from_user and is_admin(message.from_user.id):
        return True
    bot.reply_to(
        message,
        "Yeh command sirf bot admin ke liye hai.\n"
        "`.env` me `ADMIN_IDS` set karo.",
    )
    return False


def ensure_group_admin(message: Message) -> bool:
    if message.chat.type not in GROUP_TYPES:
        bot.reply_to(message, "Yeh command sirf group me use hota hai.")
        return False

    if not message.from_user:
        return False

    try:
        member = bot.get_chat_member(message.chat.id, message.from_user.id)
    except ApiTelegramException as exc:
        logger.warning(
            "Failed to check admin rights for %s in %s: %s",
            message.from_user.id,
            message.chat.id,
            exc,
        )
        bot.reply_to(message, "Admin check failed. Bot ko proper permissions do.")
        return False

    if member.status in {"administrator", "creator"}:
        return True

    bot.reply_to(message, "Sirf group admins ye command use kar sakte hain.")
    return False


def upsert_private_user(message: Message) -> None:
    if message.chat.type != "private" or not message.from_user:
        return

    user = message.from_user
    if user.is_bot:
        return

    try:
        users_collection.update_one(
            {"user_id": user.id},
            {
                "$set": {
                    "user_id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "active": True,
                    "updated_at": now_utc(),
                },
                "$setOnInsert": {"created_at": now_utc()},
            },
            upsert=True,
        )
    except PyMongoError as exc:
        logger.error("Failed to upsert private user %s: %s", user.id, exc)


def upsert_group(chat: Chat) -> None:
    if chat.type not in GROUP_TYPES:
        return

    try:
        groups_collection.update_one(
            {"group_id": chat.id},
            {
                "$set": {
                    "group_id": chat.id,
                    "title": chat.title,
                    "username": chat.username,
                    "type": chat.type,
                    "active": True,
                    "updated_at": now_utc(),
                },
                "$setOnInsert": {
                    "created_at": now_utc(),
                    "force_sub": {
                        "enabled": False,
                        "channel_ref": None,
                        "join_link": None,
                        "updated_at": now_utc(),
                        "updated_by": None,
                    },
                },
            },
            upsert=True,
        )
    except PyMongoError as exc:
        logger.error("Failed to upsert group %s: %s", chat.id, exc)


def get_group_force_sub(chat_id: int) -> dict[str, Any]:
    try:
        doc = groups_collection.find_one(
            {"group_id": chat_id},
            {"_id": 0, "force_sub": 1},
        )
    except PyMongoError as exc:
        logger.error("Failed to load force_sub config for %s: %s", chat_id, exc)
        return {"enabled": False, "channel_ref": None, "join_link": None}

    force_sub = (doc or {}).get("force_sub") or {}
    return {
        "enabled": bool(force_sub.get("enabled", False)),
        "channel_ref": force_sub.get("channel_ref"),
        "join_link": force_sub.get("join_link"),
    }


def update_group_force_sub(
    chat_id: int,
    updated_by: Optional[int],
    *,
    enabled: Optional[bool] = None,
    channel_ref: Optional[str] = None,
    join_link: Optional[str] = None,
    clear_channel: bool = False,
) -> None:
    updates: dict[str, Any] = {
        "active": True,
        "updated_at": now_utc(),
        "force_sub.updated_at": now_utc(),
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
        groups_collection.update_one({"group_id": chat_id}, {"$set": updates})
    except PyMongoError as exc:
        logger.error("Failed to update force_sub for %s: %s", chat_id, exc)


def mark_user_inactive(user_id: int) -> None:
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"active": False, "updated_at": now_utc()}},
        )
    except PyMongoError as exc:
        logger.warning("Failed to mark user %s inactive: %s", user_id, exc)


def mark_group_inactive(group_id: int) -> None:
    try:
        groups_collection.update_one(
            {"group_id": group_id},
            {"$set": {"active": False, "updated_at": now_utc()}},
        )
    except PyMongoError as exc:
        logger.warning("Failed to mark group %s inactive: %s", group_id, exc)


def is_permanent_chat_error(exc: ApiTelegramException) -> bool:
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


def extract_broadcast_text(message: Message) -> Optional[str]:
    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption
        if reply_text:
            return reply_text.strip()

    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            return parts[1].strip()

    return None


def is_valid_channel_username(value: str) -> bool:
    return bool(CHANNEL_USERNAME_RE.fullmatch(value))


def parse_channel_token(token: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "channel_ref": None,
        "join_link": None,
        "invite_only_link": False,
        "error": None,
    }
    raw = token.strip()
    if not raw:
        result["error"] = "invalid channel value"
        return result

    if raw.lstrip("-").isdigit():
        result["channel_ref"] = raw
        return result

    if raw.startswith("@"):
        username = raw[1:]
        if not is_valid_channel_username(username):
            result["error"] = "invalid username format"
            return result
        result["channel_ref"] = f"@{username}"
        result["join_link"] = f"https://t.me/{username}"
        return result

    if is_valid_channel_username(raw):
        result["channel_ref"] = f"@{raw}"
        result["join_link"] = f"https://t.me/{raw}"
        return result

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in {"t.me", "telegram.me"}:
        result["error"] = "unsupported format"
        return result

    path = parsed.path.strip("/")
    if not path:
        result["error"] = "empty telegram link"
        return result

    if path.startswith("+"):
        result["join_link"] = raw
        result["invite_only_link"] = True
        return result

    first_part = path.split("/")[0]
    if first_part.lower() == "joinchat":
        result["join_link"] = raw
        result["invite_only_link"] = True
        return result

    username = first_part.lstrip("@")
    if not is_valid_channel_username(username):
        result["error"] = "invalid telegram link"
        return result

    result["channel_ref"] = f"@{username}"
    result["join_link"] = f"https://t.me/{username}"
    return result


def resolve_fsub_inputs(args: list[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    parsed_tokens = [parse_channel_token(item) for item in args[:2]]

    for parsed in parsed_tokens:
        if parsed["error"]:
            return None, None, (
                "Invalid value. Use channel id, @username, ya t.me username link."
            )

    channel_ref = next((p["channel_ref"] for p in parsed_tokens if p["channel_ref"]), None)
    join_link = next((p["join_link"] for p in reversed(parsed_tokens) if p["join_link"]), None)
    invite_only = any(p["invite_only_link"] for p in parsed_tokens)

    if not channel_ref and not join_link:
        return None, None, (
            "Usage: /fsub <channel_id/@username/link> [optional_join_link]"
        )

    warning = None
    if invite_only and not channel_ref:
        warning = (
            "Invite link set ho gaya, lekin membership verify karne ke liye "
            "channel id ya @username bhi set karna hoga."
        )
    return channel_ref, join_link, warning


def verify_channel_ref(channel_ref: str) -> Optional[str]:
    try:
        bot.get_chat(normalize_chat_ref(channel_ref))
    except ApiTelegramException as exc:
        logger.warning("Channel verify failed for %s: %s", channel_ref, exc)
        return str(exc)
    return None


def is_joined(channel_ref: Any, user_id: int) -> bool:
    try:
        member = bot.get_chat_member(normalize_chat_ref(channel_ref), user_id)
    except ApiTelegramException as exc:
        logger.error(
            "get_chat_member failed for user %s and channel %s: %s",
            user_id,
            channel_ref,
            exc,
        )
        return True
    return member.status in JOINED_STATUSES


def should_warn(chat_id: int, user_id: int) -> bool:
    now = time.time()
    key = (chat_id, user_id)
    with _warn_lock:
        last = _warn_cache.get(key, 0)
        if now - last < WARN_COOLDOWN_SECONDS:
            return False
        _warn_cache[key] = now
        return True


def send_force_sub_warning(message: Message, join_link: Optional[str]) -> None:
    if not message.from_user:
        return

    if not should_warn(message.chat.id, message.from_user.id):
        return

    keyboard = None
    text = (
        "Aapko pehle required channel join karna hoga.\n"
        "Join karke dobara message bhejein."
    )

    if join_link:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Join Channel", url=join_link))

    try:
        bot.send_message(message.chat.id, text, reply_markup=keyboard)
    except ApiTelegramException as exc:
        logger.warning("Failed to send warning in chat %s: %s", message.chat.id, exc)


@bot.message_handler(commands=["start"])
def start_handler(message: Message) -> None:
    if message.chat.type != "private":
        return

    upsert_private_user(message)
    bot.reply_to(
        message,
        "Bot active hai.\n"
        "Aapka account save ho gaya hai, future broadcast aapko mil jayega.",
    )


@bot.message_handler(commands=["bot"])
def bot_toggle_handler(message: Message) -> None:
    if not ensure_group_admin(message):
        return

    upsert_group(message.chat)
    config = get_group_force_sub(message.chat.id)
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 1:
        status = "ON" if config["enabled"] else "OFF"
        join_link = config["join_link"] or "Not set"
        bot.reply_to(
            message,
            "ForceSub Status:\n"
            f"State: <b>{status}</b>\n"
            f"Channel: <code>{format_channel_ref(config['channel_ref'])}</code>\n"
            f"Join Link: {join_link}\n\n"
            "Use: /bot on  or  /bot off",
        )
        return

    action = parts[1].strip().lower()
    if action == "on":
        if not config["channel_ref"]:
            bot.reply_to(
                message,
                "Pehle channel set karo:\n"
                "/fsub <channel_id/@username/link>",
            )
            return
        update_group_force_sub(
            message.chat.id,
            message.from_user.id if message.from_user else None,
            enabled=True,
        )
        bot.reply_to(message, "Force-sub ON ho gaya.")
        return

    if action == "off":
        update_group_force_sub(
            message.chat.id,
            message.from_user.id if message.from_user else None,
            enabled=False,
        )
        bot.reply_to(message, "Force-sub OFF ho gaya.")
        return

    bot.reply_to(message, "Usage: /bot on  ya  /bot off")


@bot.message_handler(commands=["fsub"])
def fsub_handler(message: Message) -> None:
    if not ensure_group_admin(message):
        return

    upsert_group(message.chat)
    current_config = get_group_force_sub(message.chat.id)
    parts = (message.text or "").split(maxsplit=2)
    args = parts[1:] if len(parts) > 1 else []

    if not args:
        enabled = "ON" if current_config["enabled"] else "OFF"
        join_link = current_config["join_link"] or "Not set"
        bot.reply_to(
            message,
            "Current ForceSub Config:\n"
            f"State: <b>{enabled}</b>\n"
            f"Channel: <code>{format_channel_ref(current_config['channel_ref'])}</code>\n"
            f"Join Link: {join_link}\n\n"
            "Set: /fsub <channel_id/@username/link>\n"
            "Optional link: /fsub <channel_id/@username> <join_link>\n"
            "Clear: /fsub off",
        )
        return

    if len(args) == 1 and args[0].strip().lower() in {"off", "clear", "disable", "reset"}:
        update_group_force_sub(
            message.chat.id,
            message.from_user.id if message.from_user else None,
            enabled=False,
            clear_channel=True,
        )
        bot.reply_to(message, "Force-sub channel clear ho gaya aur status OFF kar diya.")
        return

    channel_ref, join_link, warning = resolve_fsub_inputs(args)
    if not channel_ref and not join_link:
        bot.reply_to(
            message,
            "Usage:\n"
            "/fsub <channel_id/@username/link>\n"
            "or\n"
            "/fsub <channel_id/@username> <join_link>\n\n"
            f"{warning or ''}".strip(),
        )
        return

    effective_channel_ref = channel_ref or current_config["channel_ref"]
    fields: dict[str, Any] = {}
    if channel_ref is not None:
        fields["channel_ref"] = channel_ref
    if join_link is not None:
        fields["join_link"] = join_link
    if effective_channel_ref is None:
        fields["enabled"] = False

    update_group_force_sub(
        message.chat.id,
        message.from_user.id if message.from_user else None,
        enabled=fields.get("enabled"),
        channel_ref=fields.get("channel_ref"),
        join_link=fields.get("join_link"),
    )

    reply_lines = ["Force-sub config updated for this group."]
    if effective_channel_ref:
        reply_lines.append(f"Channel: <code>{effective_channel_ref}</code>")
    if channel_ref:
        verify_error = verify_channel_ref(channel_ref)
        if verify_error:
            reply_lines.append(
                "Warning: Bot ko channel access nahi mila. "
                "Bot ko channel me add/admin karo."
            )
    if join_link:
        reply_lines.append(f"Join Link: {join_link}")
    if warning:
        reply_lines.append(warning)
    if effective_channel_ref is None:
        reply_lines.append("Note: Channel reference missing hai, isliye force-sub OFF rakha gaya.")

    bot.reply_to(message, "\n".join(reply_lines))


@bot.message_handler(commands=["stats"])
def stats_handler(message: Message) -> None:
    if not ensure_admin(message):
        return

    try:
        total_users = users_collection.count_documents({"active": True})
        total_groups = groups_collection.count_documents({"active": True})
    except PyMongoError as exc:
        logger.error("Failed to load stats: %s", exc)
        bot.reply_to(message, "Database error aaya. Logs check karo.")
        return

    bot.reply_to(
        message,
        f"Bot Stats:\nUsers: <b>{total_users}</b>\nGroups: <b>{total_groups}</b>",
    )


@bot.message_handler(commands=["broadcast"])
def broadcast_handler(message: Message) -> None:
    if not ensure_admin(message):
        return

    text = extract_broadcast_text(message)
    if not text:
        bot.reply_to(
            message,
            "Usage:\n"
            "/broadcast your message\n"
            "ya kisi text message pe reply karke /broadcast",
        )
        return

    try:
        users = list(users_collection.find({"active": True}, {"_id": 0, "user_id": 1}))
        groups = list(
            groups_collection.find({"active": True}, {"_id": 0, "group_id": 1})
        )
    except PyMongoError as exc:
        logger.error("Failed to load broadcast recipients: %s", exc)
        bot.reply_to(message, "Database error aaya. Broadcast cancel.")
        return

    total_targets = len(users) + len(groups)
    if total_targets == 0:
        bot.reply_to(message, "Broadcast recipients nahi mile.")
        return

    bot.reply_to(message, f"Broadcast start: {total_targets} chats")

    sent_users = 0
    failed_users = 0
    sent_groups = 0
    failed_groups = 0

    for user_doc in users:
        user_id = user_doc["user_id"]
        try:
            bot.send_message(user_id, text, parse_mode=None)
            sent_users += 1
        except ApiTelegramException as exc:
            failed_users += 1
            logger.warning("Broadcast failed for user %s: %s", user_id, exc)
            if is_permanent_chat_error(exc):
                mark_user_inactive(user_id)
        time.sleep(0.04)

    for group_doc in groups:
        group_id = group_doc["group_id"]
        try:
            bot.send_message(group_id, text, parse_mode=None)
            sent_groups += 1
        except ApiTelegramException as exc:
            failed_groups += 1
            logger.warning("Broadcast failed for group %s: %s", group_id, exc)
            if is_permanent_chat_error(exc):
                mark_group_inactive(group_id)
        time.sleep(0.04)

    bot.send_message(
        message.chat.id,
        "Broadcast complete:\n"
        f"Users -> Sent: {sent_users}, Failed: {failed_users}\n"
        f"Groups -> Sent: {sent_groups}, Failed: {failed_groups}",
    )


@bot.my_chat_member_handler()
def bot_chat_member_update(update) -> None:
    try:
        if update.chat.type not in GROUP_TYPES:
            return
        if (
            not update.new_chat_member
            or not update.new_chat_member.user
            or update.new_chat_member.user.id != BOT_ID
        ):
            return

        status = update.new_chat_member.status
        if status in {"member", "administrator"}:
            upsert_group(update.chat)
        elif status in {"left", "kicked"}:
            mark_group_inactive(update.chat.id)
    except Exception as exc:
        logger.warning("Failed to handle my_chat_member update: %s", exc)


@bot.message_handler(
    content_types=[
        "text",
        "audio",
        "document",
        "photo",
        "sticker",
        "video",
        "video_note",
        "voice",
        "location",
        "contact",
        "animation",
        "game",
        "poll",
        "dice",
        "venue",
    ]
)
def force_sub_handler(message: Message) -> None:
    if message.chat.type not in GROUP_TYPES:
        return

    upsert_group(message.chat)

    if message.text and message.text.startswith("/"):
        return

    if not message.from_user or message.from_user.is_bot:
        return

    config = get_group_force_sub(message.chat.id)
    if not config["enabled"] or not config["channel_ref"]:
        return

    user_id = message.from_user.id
    if is_joined(config["channel_ref"], user_id):
        return

    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException as exc:
        logger.warning(
            "Failed to delete message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            exc,
        )

    send_force_sub_warning(message, config["join_link"])


if __name__ == "__main__":
    logger.info("Force-sub bot started with per-group MongoDB config...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
