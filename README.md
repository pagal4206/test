# Telegram Force-Sub Bot (TeleBot + MongoDB)

This bot supports per-group force-sub settings stored in MongoDB.
There is no built-in default channel; each group admin sets it manually.

## Features
- Per-group force-sub configuration.
- Deletes messages from users who are not subscribed to the required channel.
- Sends a warning with an optional `Join Channel` button.
- Stores private users (`/start`) and groups in MongoDB.
- Admin tools: `/stats`, `/broadcast`.
- Group control with `/bot on` and `/bot off`.
- Built-in `/help` command with command usage guide.

## Setup
1. Install Python 3.10+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create the env file:
   ```bash
   copy .env.example .env
   ```
4. Configure `.env`:
   - `BOT_TOKEN`: BotFather token
   - `MONGO_URI`: MongoDB connection string
   - `MONGO_DB_NAME`: Database name
   - `ADMIN_IDS`: Comma-separated Telegram user IDs (for `/stats` and `/broadcast`)

## Run
```bash
python bot.py
```

## Project Structure
```text
forcesub/
|-- bot.py
|-- app/
|   |-- bot_factory.py
|   |-- config.py
|   |-- context.py
|   |-- constants.py
|   |-- database.py
|   |-- models.py
|   |-- handlers/
|   |-- services/
|   |-- repositories/
|   `-- helpers/
|-- requirements.txt
`-- .env.example
```

## Required Telegram Permissions
- Make the bot an admin in each group where force-sub is enabled.
- Enable `Delete messages` permission for the bot in those groups.
- Add the bot to the required channel (admin recommended) so membership checks can work.

## Group Commands (Group Admin Only)
- `/fsub <channel_id/@username/link>`
  - Sets the required force-sub channel for the current group.
- `/fsub <channel_id/@username> <join_link>`
  - Sets channel reference plus a custom join link button.
- `/fsub off`
  - Clears channel config and turns force-sub off.
- `/bot on`
  - Enables force-sub in current group.
- `/bot off`
  - Disables force-sub in current group.
- `/bot`
  - Shows current force-sub status for current group.
- `/help`
  - Shows full command list and usage.

## Global Commands
- `/start` (private): Saves the user in database.
- `/stats` (bot admin only): Shows active user and group counts.
- `/broadcast <message>` (bot admin only): Sends text to all active users and groups.
- Reply to any message (text/photo/video/sticker/document/voice/etc) and send `/broadcast`:
  - The bot copies that message to all active users and groups.

## Notes
- An invite-only link (`https://t.me/+...`) alone is not enough for membership verification.
- For strict enforcement, set `channel_id` or `@username`.
