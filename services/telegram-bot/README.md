# Telegram Bot

[English](README.md) | [Bahasa Indonesia](README.id.md)

Sends alerts and answers user commands.

- Language: Python 3.11
- Unit: `deploy/systemd/telegram-bot.service`
- Depends on: MariaDB, Mosquitto, Telegram Bot API

## Responsibilities

- Poll Telegram for commands and reply
- Query MariaDB for `/status`, `/last`, `/avg`, `/devices`
- Publish MQTT `cmd` messages for `/relay`
- Send pending alerts from the `alerts` table, then set `notified_at`

Full command reference and security notes: [../../docs/telegram-bot.md](../../docs/telegram-bot.md)

## Configuration

| Key | Meaning |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Comma-separated allow-list — **required** |
| `DB_*` | MariaDB credentials |
| `MQTT_*` | Broker address |
| `ALERT_COOLDOWN_SECONDS` | Minimum gap between repeat alerts |

## Run

```bash
cd services/telegram-bot
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No reply | Service down / bad token | `journalctl -u telegram-bot -n 50`; test `getMe` |
| `401 Unauthorized` | Token revoked | New token from BotFather, update `.env`, restart |
| Commands ignored | Chat id not allowed | Add to `TELEGRAM_ALLOWED_CHAT_IDS`, restart |
| Alerts never sent | `notified_at` never NULL / no rows | `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |