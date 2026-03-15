import telebot

from app.constants import GROUP_TYPES
from app.context import AppContext


def _should_send_welcome(old_status: str, new_status: str) -> bool:
    if new_status == "administrator" and old_status != "administrator":
        return True
    if old_status in {"left", "kicked"} and new_status in {"member", "administrator"}:
        return True
    return False


def _group_onboarding_text() -> str:
    return (
        "Thanks for adding me to this group.\n\n"
        "Quick setup:\n"
        "1. /fsub <channel_id/@username/link>\n"
        "2. /bot on\n"
        "3. /bot off (to disable any time)\n"
        "4. /help (command guide)\n\n"
        "I will delete messages from users who are not joined in the required channel."
    )


def register_member_update_handlers(bot: telebot.TeleBot, ctx: AppContext) -> None:
    @bot.my_chat_member_handler()
    def bot_chat_member_update(update) -> None:
        try:
            if update.chat.type not in GROUP_TYPES:
                return

            if (
                not update.new_chat_member
                or not update.new_chat_member.user
                or update.new_chat_member.user.id != ctx.bot_id
            ):
                return

            old_status = getattr(update.old_chat_member, "status", "")
            new_status = update.new_chat_member.status
            if new_status in {"member", "administrator"}:
                ctx.group_repo.upsert_group(update.chat)
                if _should_send_welcome(old_status, new_status):
                    try:
                        bot.send_message(update.chat.id, _group_onboarding_text())
                    except Exception as send_exc:
                        ctx.logger.warning(
                            "Failed to send onboarding message in chat %s: %s",
                            update.chat.id,
                            send_exc,
                        )
            elif new_status in {"left", "kicked"}:
                ctx.group_repo.mark_inactive(update.chat.id)
        except Exception as exc:
            ctx.logger.warning("Failed to handle my_chat_member update: %s", exc)
