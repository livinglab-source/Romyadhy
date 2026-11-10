# MQTT Topics (Contract)

[English](mqtt-topics.md) | [Bahasa Indonesia](mqtt-topics.id.md)

> **This document is a contract.** Firmware and Python services must agree on it.
> Changing a topic name or a payload key is a **breaking change** — bump `SCHEMA_VERSION` in the payload and note it here.

## Topic structure

```
livinglab/<device-id>/<channel>
```

| Part | Example | Rules |
|---|---|---|
| Prefix | `livinglab` | Must match `MQTT_TOPIC_PREFIX` in `.env` |
| `device-id` | `esp32-01` | Lowercase, `[a-z0-9-]` only, unique per physical board |
| `channel` | `data` | One of: `data`, `status`, `cmd`, `alert` |

## Channels

| Topic | Direction | QoS | Retain | Purpose |
|---|---|---|---|---|
| `livinglab/<device-id>/data` | device → broker | 1 | no | Sensor readings |
| `livinglab/<device-id>/status` | device → broker | 1 | **yes** | Online/offline (LWT), RSSI, uptime |
| `livinglab/<device-id>/cmd` | broker → device | 1 | no | Commands (relay on/off, interval) |
| `livinglab/<device-id>/alert` | broker → device | 1 | no | Threshold alerts from Python |

**Retain on `status` matters:** a newly started bot can read the last known state without waiting for the next publish.

## Payload: `data`

```json
{
  "schema": 1,
  "device_id": "esp32-01",
  "ts": 1731000000,
  "seq": 42,
  "temp": 27.45,
  "hum": 61.2
}
```

| Field | Type | Unit | Required | Notes |
|---|---|---|---|---|
| `schema` | int | — | yes | Bump on breaking changes |
| `device_id` | string | — | yes | Must equal the topic segment |
| `ts` | int | Unix seconds | yes | Device time (`NTP` or fallback uptime) |
| `seq` | int | — | no | Detect dropped messages |
| `temp` | float | °C | depends | 2 decimal places |
| `hum` | float | % RH | depends | 0–100 |

TODO: add the remaining fields your nodes actually publish (e.g. `soil`, `light`, `relay`, `co2`).

## Payload: `status`

```json
{
  "schema": 1,
  "device_id": "esp32-01",
  "online": true,
  "rssi": -67,
  "uptime_s": 86400,
  "fw": "1.0.0"
}
```

The device also registers a **Last Will** on this topic:

```json
{ "schema": 1, "device_id": "esp32-01", "online": false }
```

so the broker publishes it automatically if the board drops off.

## Payload: `cmd`

```json
{ "schema": 1, "action": "set_relay", "value": 1, "request_id": "abc123" }
```

| `action` | `value` | Effect |
|---|---|---|
| `set_relay` | `0` / `1` | TODO: describe |
| `set_interval` | seconds | Change publish interval |
| `reboot` | — | Restart the device |

The device should acknowledge by publishing to `status` with `last_request_id`.

## Topic naming rules

- Use the **device id**, never the board type: `livinglab/esp32-01/data` ✅, `livinglab/esp32/data` ❌
- Never include units in field names (`temp_c` is fine if you prefer it explicit — just be consistent)
- No leading slash (`/livinglab/...` creates a different tree)
- Wildcard subscribe for debugging: `mosquitto_sub -t 'livinglab/#' -v`

## Debugging

```bash
# Watch everything
mosquitto_sub -t 'livinglab/#' -v

# Watch one device
mosquitto_sub -t 'livinglab/esp32-01/#' -v

# Inspect retained status only
mosquitto_sub -t 'livinglab/+/status' -v -R

# Send a test command
mosquitto_pub -t 'livinglab/esp32-01/cmd' -m '{"schema":1,"action":"set_relay","value":1}'
```