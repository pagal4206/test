# Telegram Force-Sub Bot (TeleBot + MongoDB)

Yeh bot har group ke liye alag force-sub settings chalata hai (MongoDB me save hoti hain).  
By default koi built-in channel set nahi hota.

## Features
- Group-wise force-sub config (on/off per group).
- Non-joined users ke messages delete + warning.
- Join button support (`Join Channel`).
- MongoDB tracking:
  - Private `/start` users
  - Active groups
  - Har group ka force-sub config
- Admin panel commands:
  - `/stats`
  - `/broadcast`

## Setup
1. Python 3.10+ install karo.
2. Dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Env file banao:
   ```bash
   copy .env.example .env
   ```
4. `.env` me values set karo:
   - `BOT_TOKEN`: BotFather token
   - `MONGO_URI`: MongoDB connection string
   - `MONGO_DB_NAME`: DB name
   - `ADMIN_IDS`: comma-separated Telegram user IDs (`/stats` aur `/broadcast` ke liye)

## Run
```bash
python bot.py
```

## Telegram Permissions (Important)
- Bot ko group me admin banao.
- Group me bot ko `Delete messages` permission do.
- Jis channel ka sub-check karna hai, bot ko us channel me add/admin karna best hai.

## Group Commands (Group Admin Only)
- `/fsub <channel_id/@username/link>`
  - Is group ka force-sub channel set karta hai.
- `/fsub <channel_id/@username> <join_link>`
  - Membership check ke liye channel_ref + button ke liye custom join link set karta hai.
- `/fsub off`
  - Is group ka force-sub channel clear + force-sub off.
- `/bot on`
  - Is group me force-sub enable.
- `/bot off`
  - Is group me force-sub disable.
- `/bot`
  - Current group status show karta hai.

## Global Commands
- `/start` (private): user ko DB me add karta hai.
- `/stats` (bot admin only): active users + groups count.
- `/broadcast <message>` (bot admin only): sab active users + groups ko message bhejta hai.

## Notes
- Agar sirf private invite link (`https://t.me/+...`) set kiya gaya ho, to membership verify nahi ho sakti.
- Proper force-sub ke liye `channel_id` ya `@username` dena zaroori hai.
