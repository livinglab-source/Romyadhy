# Telegram Bot

[English](README.md) | [Bahasa Indonesia](README.id.md)

Entry point: [`telegrambot.py`](telegrambot.py)

Chat-based control and monitoring for the hydroponic Living Lab: live sensor dashboard, relay control, calibration, CSV export, and alerts.

## Responsibilities

- Subscribe to MQTT sensor data, keep the latest reading in memory, render an ASCII dashboard
- Control 6 relays and switch the system between `auto` / `manual`
- Drive TDS and turbidity calibration sequences on the ESP32
- Log relay ON/OFF events with duration into MariaDB
- Export DB tables to CSV and send them as Telegram documents
- Push alerts (threshold breaches, mode changes, calibration status)

It does **not** write sensor readings to the database — that is `data-logger`'s job.

## 1. Configuration

Everything is read from the environment. The bot never contains secrets.

```bash
cp ../../.env.example ../../.env     # once, at repo root
```

| Key | Required | Default | Meaning |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — | From @BotFather |
| `TELEGRAM_CHAT_ID` | yes | — | Chat for scheduled updates and alerts |
| `TELEGRAM_ALLOWED_CHAT_IDS` | no | = `TELEGRAM_CHAT_ID` | Comma-separated ids allowed to command the bot |
| `ACCESS_PASSWORD` | yes | — | Password for `/login` |
| `SESSION_TIMEOUT_SECONDS` | no | `3600` | Session expires after this much inactivity |
| `MQTT_HOST` / `MQTT_PORT` | no | `127.0.0.1` / `1883` | Broker address |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | no | — | Broker credentials |
| `MQTT_TOPIC_PREFIX` | no | `smartgreengarden` | Root of every topic |
| `DB_HOST` / `DB_PORT` | no | `127.0.0.1` / `3306` | MariaDB address |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | yes | — | MariaDB credentials |
| `DB_TABLE` | no | `hydroponic_water_data_romy` | Sensor data table |
| `DB_TIME_COLUMN` | no | `datetime` | Timestamp column |
| `DB_TIME_IS_STRING` | no | `false` | Set `true` if the timestamp is stored as text |
| `EXPORT_DIR` | no | `./exports` | Where CSVs are written before sending |
| `LOG_DIR` | no | `./logs` | Log file location |
| `ALLOW_DEV_MODE` | no | `false` | Simulate sensor data if MQTT is unreachable |

> If MQTT is unreachable and `ALLOW_DEV_MODE` is not `true`, the bot exits instead of silently pretending to have data.

## 2. Run

```bash
cd services/telegram-bot
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -r requirements.txt
python telegrambot.py
```

Or from the repo root: `scripts/run_services.sh`.

Under systemd: `deploy/systemd/telegram-bot.service`.

Dependencies are pinned in [`requirements.txt`](requirements.txt) — note `mysql-connector-python`, which provides the `mysql.connector` import.

## 3. Authentication

Every command except `/login` and `/logout` requires a session.

| Command | Effect |
|---|---|
| `/login <password>` | Starts a session; the message is deleted immediately so the password does not stay in chat |
| `/logout` | Ends the session |

Sessions expire after `SESSION_TIMEOUT_SECONDS` of inactivity and are refreshed on each command. Inline keyboard callbacks check the session too, so an expired panel cannot be used.

## 4. Commands

### Monitoring

| Command | What it returns |
|---|---|
| `/all_data` | Full dashboard: water quality, sensors, 4 tank bars with sparklines |
| `/tanks` | Side-by-side visual comparison of the 4 tanks |
| `/status` | Mode, relay states, data freshness, DB row counts |
| `/tds1`, `/tds2` | TDS reading, gauge, health verdict, min/max/avg |
| `/turbidity` | Turbidity gauge and condition |
| `/delta_tds` | Nutrient difference meter |
| `/flowrate` | Flow rate stat card |
| `/level1` … `/level4` | Per-tank level card |
| `/water_quality` | Water classification |

### Relay and mode

| Command | Example |
|---|---|
| `/relaypanel` | Interactive ON/OFF buttons for all relays |
| `/relay <name> <on\|off>` | `/relay irigasi on` |
| `/relaylog <name> [count]` | `/relaylog irigasi 10` |
| `/relaystats [name] [week]` | `/relaystats irigasi week` |
| `/mode <auto\|manual>` | `/mode manual` |

Relay names: `irigasi`, `kuras_tandon`, `kuras`, `pengaduk`, `valve_tandon`, `pompa_kuras`.

**Relay commands are refused while the system is in `auto` mode.** Switch with `/mode manual` first — this prevents manual actions fighting the automation.

### Calibration

| Command | Effect |
|---|---|
| `/cal_tds1 start` | Begin TDS1 multi-point calibration |
| `/cal_tds1 set <ppm>` | Record the current point (0–5000) |
| `/cal_tds1 single <ppm>` | Single-point calibration |
| `/cal_tds2 ...` | Same, for TDS2 |
| `/calturb` | Start turbidity calibration (0 / 50 / 100 NTU) |
| `/next` | Record the next turbidity point |
| `/cancelcal` | Abort turbidity calibration |

### Database and export

| Command | Effect |
|---|---|
| `/dbstatus` | Ping the connection pool |
| `/dbstatus reconnect` | Rebuild the pool after a DB outage |
| `/export list` | Show exportable tables |
| `/export <table> [days]` | Preview row count, then confirm to send CSV |
| `/help` | Full command list |

Exportable tables: `sensor_data`, `relay_logs`. The CSV is deleted from disk after sending.

## 5. MQTT contract

Topics are built from `MQTT_TOPIC_PREFIX` (default `smartgreengarden`).

### Subscribed

| Topic | Payload | Used for |
|---|---|---|
| `<prefix>/sensor/data` | JSON: `tds1`, `tds2`, `delta_tds`, `turbidity`, `flowrate`, `level1`–`level4`, `water_quality` | Live dashboard |
| `<prefix>/notification` | `{"alert": "...", "level": "warning"}` | Alerts to Telegram |
| `<prefix>/sensor/calibrate/turbidity/status` | text | Calibration progress messages |
| `<prefix>/system/mode` | `auto` / `manual` | Keeps bot state in sync with firmware |
| `<prefix>/relay/<name>/command` | `1` / `0` | Reflects relay state changed by automation |

`level` may be `critical`, `warning`, `info`, or `system`; if omitted the bot infers it from the message text.

### Published

| Topic | Payload | Trigger |
|---|---|---|
| `<prefix>/sensor/request_data` | `1` | `/all_data`, refresh button |
| `<prefix>/system/mode` | `auto` / `manual` | `/mode` |
| `<prefix>/relay/pompa_irigasi/command` | `1` / `0` | `/relay irigasi …` |
| `<prefix>/relay/pengurasan_tandon/command` | `1` / `0` | `kuras_tandon` |
| `<prefix>/relay/pengurasan/command` | `1` / `0` | `kuras` |
| `<prefix>/relay/pengaduk_tandon/command` | `1` / `0` | `pengaduk` |
| `<prefix>/relay/valve_tandon/command` | `1` / `0` | `valve_tandon` |
| `<prefix>/relay/pompa_kuras/command` | `1` / `0` | `pompa_kuras` |
| `<prefix>/sensor/calibrate/tds1/multi/start` | `1` | `/cal_tds1 start` |
| `<prefix>/sensor/calibrate/tds1/multi/set` | `<ppm>` | `/cal_tds1 set` |
| `<prefix>/sensor/kalibrasi/tds1` | `<ppm>` | `/cal_tds1 single` |
| `<prefix>/sensor/calibrate/tds2/multi/start` | `1` | `/cal_tds2 start` |
| `<prefix>/sensor/calibrate/tds2/multi/set` | `<ppm>` | `/cal_tds2 set` |
| `<prefix>/sensor/kalibrasi/tds2` | `<ppm>` | `/cal_tds2 single` |
| `<prefix>/sensor/calibrate/turbidity/start` | `1` | `/calturb` |
| `<prefix>/sensor/calibrate/turbidity/next` | `1` | `/next` |
| `<prefix>/sensor/calibrate/turbidity/cancel` | `1` | `/cancelcal` |

Example sensor payload:

```json
{
  "tds1": 812.4,
  "tds2": 795.1,
  "delta_tds": 17.3,
  "turbidity": 12.5,
  "flowrate": 6.2,
  "level1": 88,
  "level2": 64,
  "level3": 41,
  "level4": 27,
  "water_quality": "2"
}
```

`water_quality` codes: `0` cloudy/nutrient, `1` cloudy/sediment, `2` normal, `3` nutrient imbalance, `4` water level low. The bot recomputes this from the raw values so a stale code in the payload cannot mislead the display.

## 6. Database tables used

| Table | Purpose | Columns used |
|---|---|---|
| `hydroponic_water_data_romy` | Sensor history (`DB_TABLE`) | `datetime`, sensor columns; counted and read for export |
| `relay_logs` | Relay event log | `relay_name`, `state`, `event_time`, `duration_seconds`, `mode` |

The bot creates neither table; they must exist. See [../../docs/database.md](../../docs/database.md).

## 7. Behaviour worth knowing

| Behaviour | Detail |
|---|---|
| Alert queue | Messages are queued in memory (not persisted) and drained every 5 s |
| Calibration status | Drained every 1 s |
| Scheduled dashboard | Full sensor message every 300 s to `TELEGRAM_CHAT_ID` |
| Freshness badge | 🟢 <30 s, 🟡 <5 min, 🔴 older — shows "cek ESP32" |
| Sparklines | Last 10 readings per sensor, in memory only |
| Invalid values | `nan` in any payload is replaced with `0.0` before parsing |
| `message is not modified` | Suppressed so refresh buttons do not raise |

Anything held only in memory (sparkline history, alert queue, relay ON timers) is lost on restart. The `relay_logs` table is the durable record.

## 8. Security

- The token, DB password, and login password are **environment variables only**. Do not paste them back into the source.
- Keep `TELEGRAM_ALLOWED_CHAT_IDS` narrow. Anyone in that list can control pumps.
- `/login` deletes the password message, but Telegram history is not a secret store — rotate `ACCESS_PASSWORD` rather than reusing it elsewhere.
- Logs are written under `LOG_DIR`; they contain chat ids and command text, so they are git-ignored.
- If a token ever leaks: `/revoke` in @BotFather, issue a new token, update `.env`, `systemctl restart telegram-bot`.

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: Missing required environment variable` | `.env` not loaded | Ensure `EnvironmentFile=` in the unit, or run from the repo root |
| Bot starts then exits | MQTT unreachable and `ALLOW_DEV_MODE=false` | Start the broker, fix `MQTT_HOST`, or set `ALLOW_DEV_MODE=true` for a demo |
| `ModuleNotFoundError: mysql` | Wrong package installed | `pip install -r requirements.txt` (needs `mysql-connector-python`) |
| No reply to commands | Not logged in | `/login <password>` |
| "Access Denied" after working earlier | Session timed out | Log in again |
| Relay buttons do nothing | System in `auto` mode | `/mode manual` |
| `/dbstatus` shows error | DB down, bad credentials, or pool never built | Check `DB_*`, then `/dbstatus reconnect` |
| Export says 0 rows | Wrong table key or date range | `/export list`, try without a day limit |
| Alerts never arrive | Firmware not publishing, or no alert rows | Check `mosquitto_sub -t '<prefix>/notification' -v` |
| Dashboard shows "belum ada data" | No sensor payload received yet | Verify `<prefix>/sensor/data` |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)