# Wemos Gateway

[English](README.md) | [Bahasa Indonesia](README.id.md)

TODO: one sentence describing what this board actually does (relay control? second sensor node? MQTT gateway?).

- Role: TODO
- Board: Wemos D1 mini (ESP8266)
- Device id: `wemos-01`

## Responsibilities

- TODO — role not confirmed yet
- Subscribe to the relay command topics it owns: `smartgreengarden/relay/<name>/command`
- Publish its state back to the same topic so the bot stays in sync

> The Wemos role is still undecided. Do not invent new topics: reuse the contract in [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md).

## Hardware

| Component | Model | Notes |
|---|---|---|
| MCU | Wemos D1 mini | ESP8266, 2.4 GHz WiFi only |
| TODO | TODO | TODO |

Wiring: [../../docs/hardware.md](../../docs/hardware.md#wiring--wemos-gateway)

## Configuration

```bash
cp include/config.h.example include/config.h
```

| Key | Meaning |
|---|---|
| `WIFI_SSID` / `WIFI_PASSWORD` | Lab WiFi (2.4 GHz) |
| `MQTT_HOST` / `MQTT_PORT` | Raspberry Pi broker |
| `MQTT_USER` / `MQTT_PASS` | Mosquitto credentials |
| `DEVICE_ID` | `wemos-01` |

## MQTT

| Direction | Topic | Payload |
|---|---|---|
| subscribe | `smartgreengarden/relay/<name>/command` | `1` / `0` |
| publish | `smartgreengarden/relay/<name>/command` | `1` / `0` (state echo) |

> Topic names are fixed by the contract; the role of this board determines which `<name>` it handles. See [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md).

## Build and flash

```bash
pio run
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Won't connect | 2.4 GHz only; check credentials |
| Relay does not switch | Verify pin in wiring table matches firmware |
| Duplicate client id | `DEVICE_ID` must be unique |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)