# MQTT Bridge

[English](README.md) | [Bahasa Indonesia](README.id.md)

Subscribes to `smartgreengarden/#`, validates and normalizes payloads, forwards clean readings to the data logger.

- Language: Python 3.11
- Unit: `deploy/systemd/mqtt-bridge.service`
- Depends on: Mosquitto (`MQTT_*` in `.env`)

## Responsibilities

- Subscribe to `smartgreengarden/+/data` and `smartgreengarden/+/status`
- Reject malformed payloads (missing fields, out-of-range values, wrong `schema`)
- Normalize units and types before forwarding
- Log a warning with the raw payload when validation fails

Does **not** write to the database and does **not** call Telegram.

## Configuration

| Key | Meaning |
|---|---|
| `MQTT_HOST` / `MQTT_PORT` | Broker address |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | Broker credentials |
| `MQTT_TOPIC_PREFIX` | Default `livinglab` |
| `LOG_LEVEL` | `INFO` normally, `DEBUG` when validating payloads |

## Run

```bash
cd services/mqtt-bridge
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Debug

```bash
mosquitto_sub -t 'smartgreengarden/#' -v          # is anything arriving?
journalctl -u mqtt-bridge -f               # on the Pi
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Starts then exits | Missing env var | `KeyError` in the log — check `.env` |
| No messages | Wrong prefix or credentials | Confirm `MQTT_TOPIC_PREFIX`, test with `mosquitto_sub` |
| Everything rejected | `schema` mismatch with firmware | Align with [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md) |