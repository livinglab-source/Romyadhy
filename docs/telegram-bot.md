# Telegram Bot

[English](telegram-bot.md) | [Bahasa Indonesia](telegram-bot.id.md)

Code: [`services/telegram-bot/`](../services/telegram-bot/)

## What it does

Two directions:

1. **Outbound** — sends alerts (threshold breach, device offline) into a Telegram chat.
2. **Inbound** — answers commands by querying MariaDB or publishing MQTT commands.

## Setup

1. Talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Put it in `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

3. Find your chat id: message the bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
4. **Always set `TELEGRAM_ALLOWED_CHAT_IDS`.** Without it, anyone who finds the bot can command your devices.

## Commands

| Command | Example | What it returns |
|---|---|---|
| `/start` | `/start` | Short help |
| `/status <device>` | `/status esp32-01` | Online/offline, RSSI, last seen |
| `/last <device>` | `/last esp32-01` | Latest reading |
| `/avg <device> <hours>` | `/avg esp32-01 24` | Average temp/humidity |
| `/devices` | `/devices` | List of registered devices |
| `/relay <device> <0\|1>` | `/relay wemos-01 1` | Publishes an MQTT `cmd` |
| `/alert <temp> <hum>` | `/alert 30 80` | Sets thresholds (TODO: persisted where?) |

TODO: confirm this command list against the implemented code and delete rows that do not exist.

## Alert rules

| Rule | Trigger | Cooldown |
|---|---|---|
| Temperature high | `temp_c > threshold` | `ALERT_COOLDOWN_SECONDS` |
| Device offline | `last_seen` older than N minutes | once per transition |

Cooldown prevents a chat flood: one notification per rule per cooldown window, not per message.

The bot picks up work from the `alerts` table:

```sql
SELECT id, device_id, kind, message
FROM alerts WHERE notified_at IS NULL ORDER BY created_at LIMIT 20;
```

then sets `notified_at = NOW(3)` after a successful send. A failed send leaves the row pending — the retry does not need new code.

## Security notes

- Token in `.env` only, never in code or docs.
- Allowed chat id list is the only authorization — there are no per-user roles.
- If the token leaks: `/revoke` in BotFather, issue a new one, update `.env`, restart the service.
- Do not log full API responses at `INFO`; they contain the token in the URL.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Bot silent | Service down | `systemctl status telegram-bot`, `journalctl -u telegram-bot -n 50` |
| `401 Unauthorized` | Wrong/revoked token | Re-check `.env`, restart |
| Commands ignored | Your chat id not in `TELEGRAM_ALLOWED_CHAT_IDS` | Add it, restart |
| Alerts never arrive | `notified_at` never NULL / no alert rows created | Check the alert rule in the bridge, then `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |