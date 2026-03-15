import telebot
from telebot.apihelper import ApiTelegramException
from telebot.types import Message

from app.constants import GROUP_TYPES
from app.context import AppContext
from app.helpers.channel_parser import resolve_fsub_inputs


def _fsub_help_text() -> str:
    return (
        "Usage:\n"
        "/fsub <channel_id/@username/link>\n"
        "or\n"
        "/fsub <channel_id/@username> <join_link>"
    )


def _bot_status_text(ctx: AppContext, chat_id: int) -> str:
    config = ctx.group_repo.get_force_sub(chat_id)
    status = "ON" if config.enabled else "OFF"
    join_link = config.join_link or "Not set"
    channel = ctx.force_sub_service.format_channel_ref(config.channel_ref)
    return (
        "Force-Sub Status\n"
        f"Status: <b>{status}</b>\n"
        f"Channel: <code>{channel}</code>\n"
        f"Join Link: {join_link}\n\n"
        "Use /bot on or /bot off."
    )


def _parse_bot_action(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().lower()


def register_group_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    @bot.message_handler(commands=["bot"])
    def bot_handler(message: Message) -> None:
        if not ctx.auth_service.ensure_group_admin(message):
            return

        ctx.group_repo.upsert_group(message.chat)
        action = _parse_bot_action(message)
        config = ctx.group_repo.get_force_sub(message.chat.id)

        if action == "on":
            if not config.channel_ref:
                bot.reply_to(message, "Please set a channel first using /fsub.")
                return
            ctx.group_repo.update_force_sub(
                message.chat.id,
                message.from_user.id if message.from_user else None,
                enabled=True,
            )
            bot.reply_to(message, "Force-sub enabled.")
            return

        if action == "off":
            ctx.group_repo.update_force_sub(
                message.chat.id,
                message.from_user.id if message.from_user else None,
                enabled=False,
            )
            bot.reply_to(message, "Force-sub disabled.")
            return

        if action:
            bot.reply_to(message, "Usage: /bot on or /bot off")
            return

        bot.reply_to(message, _bot_status_text(ctx, message.chat.id))

    @bot.message_handler(commands=["fsub"])
    def fsub_handler(message: Message) -> None:
        if not ctx.auth_service.ensure_group_admin(message):
            return

        ctx.group_repo.upsert_group(message.chat)
        current_config = ctx.group_repo.get_force_sub(message.chat.id)
        parts = (message.text or "").split(maxsplit=2)
        args = parts[1:] if len(parts) > 1 else []

        if not args:
            enabled = "ON" if current_config.enabled else "OFF"
            join_link = current_config.join_link or "Not set"
            bot.reply_to(
                message,
                "Current Force-Sub Config:\n"
                f"Status: <b>{enabled}</b>\n"
                f"Channel: <code>{ctx.force_sub_service.format_channel_ref(current_config.channel_ref)}</code>\n"
                f"Join Link: {join_link}\n\n"
                "Set: /fsub <channel_id/@username/link>\n"
                "Optional link: /fsub <channel_id/@username> <join_link>\n"
                "Clear: /fsub off",
            )
            return

        if len(args) == 1 and args[0].strip().lower() in {"off", "clear", "disable", "reset"}:
            ctx.group_repo.update_force_sub(
                message.chat.id,
                message.from_user.id if message.from_user else None,
                enabled=False,
                clear_channel=True,
            )
            bot.reply_to(message, "Force-sub channel was cleared and status is now OFF.")
            return

        channel_ref, join_link, notice = resolve_fsub_inputs(args)
        if not channel_ref and not join_link:
            response = _fsub_help_text()
            if notice:
                response = f"{response}\n\n{notice}"
            bot.reply_to(message, response)
            return

        effective_channel_ref = channel_ref or current_config.channel_ref
        if notice and effective_channel_ref:
            notice = None
        enabled = None if effective_channel_ref else False
        ctx.group_repo.update_force_sub(
            message.chat.id,
            message.from_user.id if message.from_user else None,
            enabled=enabled,
            channel_ref=channel_ref,
            join_link=join_link,
        )

        reply_lines = ["Force-sub configuration was updated for this group."]
        if effective_channel_ref:
            reply_lines.append(f"Channel: <code>{effective_channel_ref}</code>")
        if channel_ref:
            verify_error = ctx.force_sub_service.verify_channel_ref(channel_ref)
            if verify_error:
                reply_lines.append(
                    "Warning: Bot cannot access this channel yet. "
                    "Add the bot to the channel (preferably as admin)."
                )
        if join_link:
            reply_lines.append(f"Join Link: {join_link}")
        if notice:
            reply_lines.append(notice)
        if not effective_channel_ref:
            reply_lines.append(
                "Note: No channel reference is set, so force-sub remains OFF."
            )

        bot.reply_to(message, "\n".join(reply_lines))

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

        ctx.group_repo.upsert_group(message.chat)

        if message.text and message.text.startswith("/"):
            return

        if not message.from_user or message.from_user.is_bot:
            return

        config = ctx.group_repo.get_force_sub(message.chat.id)
        if not config.enabled or not config.channel_ref:
            return

        if ctx.force_sub_service.is_joined(config.channel_ref, message.from_user.id):
            return

        try:
            bot.delete_message(message.chat.id, message.message_id)
        except ApiTelegramException as exc:
            ctx.logger.warning(
                "Failed to delete message %s in chat %s: %s",
                message.message_id,
                message.chat.id,
                exc,
            )

        ctx.force_sub_service.send_force_sub_warning(message, config.join_link)

