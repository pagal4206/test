from app.bot_factory import create_app


def main() -> None:
    ctx = create_app()
    ctx.logger.info("Force-sub bot started with modular structure...")
    ctx.bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()

