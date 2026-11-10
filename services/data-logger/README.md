# Data Logger

[English](README.md) | [Bahasa Indonesia](README.id.md)

Persists sensor readings into MariaDB.

- Language: Python 3.11
- Unit: `deploy/systemd/data-logger.service`
- Depends on: Mosquitto, MariaDB

## Responsibilities

- Receive validated readings from the bridge
- Insert into `readings` with the correct column types
- Upsert `device_status` on every `status` message
- Keep running if the DB is briefly unavailable (retry, do not crash)

Does **not** validate payload shape (the bridge owns that) and does **not** send notifications.

## Configuration

| Key | Meaning |
|---|---|
| `DB_HOST` / `DB_PORT` | MariaDB address |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Credentials |
| `MQTT_HOST` / `MQTT_PORT` | Broker address |
| `LOG_LEVEL` | `INFO` normally |

## Run

```bash
cd services/data-logger
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Verify

```bash
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM readings;"
mysql -u livinglab -p livinglab -e "SELECT * FROM readings ORDER BY id DESC LIMIT 5;"
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Count stays 0 | Not receiving / insert failing | Check logs for SQL errors |
| FK error on insert | Device not in `devices` | `INSERT INTO devices (device_id, board_type, role) VALUES (...)` |
| `Incorrect decimal value` | Value out of `DECIMAL(5,2)` range | Fix the payload or widen the column via a migration |
| Slow inserts | Missing index / huge table | Confirm `idx_readings_device_time`; apply retention |

Schema reference: [../../db/schema.sql](../../db/schema.sql) · [../../docs/database.md](../../docs/database.md)