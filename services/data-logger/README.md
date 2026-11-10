# Data Logger

[English](README.md) | [Bahasa Indonesia](README.id.md)

Entry point: [`dataSave.py`](dataSave.py)

Subscribes to the sensor topic and persists each reading to MariaDB, with an optional mirror to Firebase Realtime Database.

## Responsibilities

- Subscribe to `<prefix>/sensor/data`
- Create the `hydroponic_water_data_romy` table if it does not exist
- Flatten the JSON payload into one row, deriving tank level categories
- Insert into MariaDB **and**, if configured, write the same record to Firebase RTDB
- Log a warning when no message has arrived for longer than expected (watchdog)

This is the **only** service that writes sensor readings. There is no separate bridge — the logger subscribes directly.

## 1. Configuration

All values come from the environment; the file contains no secrets.

```bash
cp ../../.env.example ../../.env     # once, at repo root
```

| Key | Required | Default | Meaning |
|---|---|---|---|
| `MQTT_HOST` / `MQTT_PORT` | no | `localhost` / `1883` | Broker address |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | no | — | Broker credentials |
| `MQTT_TOPIC_PREFIX` | no | `smartgreengarden` | Topic root |
| `DB_HOST` / `DB_PORT` | no | `localhost` / `3306` | MariaDB address |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | **yes** | — | MariaDB credentials |
| `DB_TABLE` | no | `hydroponic_water_data_romy` | Target table |
| `SAVE_THROTTLE_SECONDS` | no | `60` | Minimum gap between saved rows |
| `EXPECTED_INTERVAL_SECONDS` | no | `300` | Watchdog threshold |
| `LOG_DIR` | no | `./logs` | Log location |
| `LOG_BACKUP_COUNT` | no | `30` | Rotated log files to keep |
| `FIREBASE_CRED_PATH` | no | — | Service-account JSON; empty disables cloud upload |
| `FIREBASE_DATABASE_URL` | no | — | RTDB URL |
| `FIREBASE_RTDB_ROOT` | no | `Hydroponic_Data` | Root path in RTDB |

> Firebase is optional. With `FIREBASE_CRED_PATH` empty the logger still works — it just skips the cloud write and logs a warning once.

## 2. Run

```bash
cd services/data-logger
pip install -r requirements.txt
python dataSave.py
```

Or from the repo root: `scripts/run_services.sh`. Under systemd: `deploy/systemd/data-logger.service`.

Missing `DB_*` values stop the process immediately with `RuntimeError: Missing required environment variable`.

## 3. Payload → columns

Input on `<prefix>/sensor/data`:

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

| Payload key | Column | Notes |
|---|---|---|
| — | `datetime` | Server time at insert (`datetime.now()`) |
| `tds1` | `tds1_ppm` | DECIMAL(10,2) |
| `tds2` | `tds2_ppm` | DECIMAL(10,2) |
| `delta_tds` | `delta_tds` | DECIMAL(5,2) |
| `turbidity` | `turbidity` | DECIMAL(10,2) |
| `flowrate` (or `flowRate`) | `flow_rate` | Both spellings accepted |
| `level1`–`level4` | `water_level_N_percent` | DECIMAL(5,2) |
| `level1`–`level4` | `water_level_N_status` | Derived: Empty / Low / Medium / High / Full |
| `water_quality` | `water_quality` | Stored as the **integer code** (0–4, `-1` unknown) |
| cloud result | `uploaded_to_cloud` | `1` if the Firebase write succeeded |

Missing keys default to `0.0` rather than failing the row, so a partial payload still lands in the table.

### Level categories

| Percent | Category |
|---|---|
| ≤ 0 | Empty |
| ≤ 25 | Low |
| ≤ 50 | Medium |
| ≤ 75 | High |
| > 75 | Full |

Note this differs from the bot's display thresholds (30 / 75 / 100). They are independent by design; do not assume they match.

## 4. Throttling

`on_message` records `last_message_time` for **every** message (so the watchdog sees traffic), but only writes a row if `SAVE_THROTTLE_SECONDS` has elapsed since the last save.

| Situation | Result |
|---|---|
| ESP32 publishes every 5 s | One row per minute |
| Broker down | No rows; watchdog warns after `EXPECTED_INTERVAL_SECONDS` |
| Retained message at startup | Saved immediately (first message always passes) |

Skipped messages are logged at `INFO`: `⏭️ Message received but skipped (within 60s throttle window)`.

## 5. Firebase mirror

When enabled, each record is also written to:

```
<FIREBASE_RTDB_ROOT>/<YYYY-MM-DD>/<HH-MM>
```

One node per minute, overwritten if two records land in the same minute. The record contains the same fields as the MySQL row plus `timestamp_iso`.

A failed cloud write does **not** block the MySQL insert — it is logged and `uploaded_to_cloud` is set to `0`. That column is your reconciliation marker: `SELECT * FROM hydroponic_water_data_romy WHERE uploaded_to_cloud = 0;`

The credential JSON is a private key. It is git-ignored (`*firebase*adminsdk*.json`) and must never be committed.

## 6. Logging

| Property | Value |
|---|---|
| File | `LOG_DIR/garden.log` |
| Rotation | Daily at midnight |
| Compression | gzipped (`.gz`) |
| Retention | `LOG_BACKUP_COUNT` files |
| Console | mirrored at the same level |

Watchdog messages look like:

```
⏰ No MQTT message received for 412s (expected every ~300s).
```

That line is the evidence that a gap in the data is a sensor/network problem, not a silent logger failure.

## 7. Verify

```bash
mysql -u livinglab -p livinglab -e "SELECT * FROM hydroponic_water_data_romy ORDER BY id DESC LIMIT 5;"
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM hydroponic_water_data_romy;"
tail -f services/data-logger/logs/garden.log
```

Healthy log sequence:

```
✅ Successfully connected to Local MQTT Broker
📥 Listening to topic: smartgreengarden/sensor/data
📩 [2026-11-10 14:30:02] Message received and PROCESSING...
🗄️ Data successfully saved to MySQL.
```

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: Missing required environment variable` | `.env` not loaded | `EnvironmentFile=` in the unit, or run from repo root |
| `Error setting up database` then exit | DB down or wrong credentials | Check `DB_*`, `systemctl status mariadb` |
| Connects but no rows | Wrong topic prefix | Compare `MQTT_TOPIC_PREFIX` with firmware, check with `mosquitto_sub` |
| Rows appear at most once per minute | Throttle working as intended | Lower `SAVE_THROTTLE_SECONDS` for testing |
| `Error processing JSON data` | Malformed payload | Fix the sender; raw payload is logged |
| `flow_rate` is always 0 | Payload uses a different key | Send `flowrate` or `flowRate` |
| `water_quality` is -1 | Missing or non-numeric value | Check the ESP32 classification output |
| `uploaded_to_cloud` always 0 | Firebase not configured or failing | Check `FIREBASE_*`, read the logged reason |
| No watchdog warnings but no data | Logger not started | `systemctl status data-logger` |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)