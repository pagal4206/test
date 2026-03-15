import telebot
from telebot.types import Message

from app.context import AppContext


def register_admin_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    @bot.message_handler(commands=["stats"])
    def stats_handler(message: Message) -> None:
        if not ctx.auth_service.ensure_bot_admin(message):
            return

        total_users = ctx.user_repo.count_active()
        total_groups = ctx.group_repo.count_active()

        bot.reply_to(
            message,
            f"Bot Stats:\nUsers: <b>{total_users}</b>\nGroups: <b>{total_groups}</b>",
        )

    @bot.message_handler(commands=["broadcast"])
    def broadcast_handler(message: Message) -> None:
        if not ctx.auth_service.ensure_bot_admin(message):
            return

        payload = ctx.broadcast_service.build_payload(message)
        if not payload:
            bot.reply_to(
                message,
                "Usage:\n"
                "/broadcast your text message\n"
                "or reply to any message (text/photo/video/sticker/document/etc) and send /broadcast",
            )
            return

        total_targets = len(ctx.user_repo.list_active_ids()) + len(ctx.group_repo.list_active_ids())
        if total_targets == 0:
            bot.reply_to(message, "No broadcast recipients were found.")
            return

        bot.reply_to(message, f"Broadcast start: {total_targets} chats")
        summary = ctx.broadcast_service.broadcast(payload)
        bot.send_message(
            message.chat.id,
            "Broadcast complete:\n"
            f"Users -> Sent: {summary.sent_users}, Failed: {summary.failed_users}\n"
            f"Groups -> Sent: {summary.sent_groups}, Failed: {summary.failed_groups}",
        )
