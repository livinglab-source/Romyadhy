# ESP32 Sensor Node

[English](README.md) | [Bahasa Indonesia](README.id.md)

Reads environment sensors and publishes readings to MQTT every `PUBLISH_INTERVAL_MS`.

- Role: sensor node
- Board: ESP32 — TODO: exact variant (e.g. DevKit V1 / WROOM-32)
- Device id: `esp32-01` — TODO: make unique if you have more than one

## Responsibilities

- Read TODO: sensor list (e.g. DHT22 temperature/humidity, BME280)
- Publish `livinglab/esp32-01/data` every N seconds
- Publish `livinglab/esp32-01/status` (retained) + register a Last Will
- Subscribe to `livinglab/esp32-01/cmd` and act on it

## Hardware

| Component | Model | Notes |
|---|---|---|
| MCU | ESP32 TODO | 2.4 GHz WiFi only |
| Sensor | TODO | TODO: voltage, protocol (one-wire / I2C) |
| Power | TODO | Use a supply that handles WiFi current spikes |

Wiring table: [../../docs/hardware.md](../../docs/hardware.md#wiring--esp32-sensor-node)

## Configuration

Secrets are not committed. Create `include/config.h` from the example:

```bash
cp include/config.h.example include/config.h
```

| Key | Where | Meaning |
|---|---|---|
| `WIFI_SSID` / `WIFI_PASSWORD` | `include/config.h` | Lab WiFi (2.4 GHz) |
| `MQTT_HOST` | `include/config.h` | Raspberry Pi LAN IP |
| `MQTT_PORT` | `include/config.h` | `1883` |
| `MQTT_USER` / `MQTT_PASS` | `include/config.h` | Mosquitto credentials |
| `DEVICE_ID` | `include/config.h` | Must match the topic segment |
| `PUBLISH_INTERVAL_MS` | `include/config.h` | Default 30000 |
| `FW_VERSION` | `platformio.ini` build flag | Sent in `status` |

## MQTT

Contract: [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md)

| Direction | Topic | Payload |
|---|---|---|
| publish | `livinglab/esp32-01/data` | `{"schema":1,"device_id":"esp32-01","ts":...,"temp":27.45,"hum":61.2}` |
| publish (retained) | `livinglab/esp32-01/status` | `{"schema":1,"online":true,"rssi":-67,"uptime_s":...,"fw":"1.0.0"}` |
| subscribe | `livinglab/esp32-01/cmd` | `{"schema":1,"action":"set_interval","value":10000}` |

Last Will on `status`: `{"schema":1,"device_id":"esp32-01","online":false}`

## Build and flash

```bash
pio run                  # compile
pio run -t upload        # flash over USB
pio device monitor -b 115200
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Boot loop / brownout | Power supply too weak | Better PSU, capacitor near 3V3 |
| WiFi never connects | 5 GHz network or typo | Use 2.4 GHz; recheck `WIFI_SSID` |
| MQTT keeps reconnecting | Duplicate `DEVICE_ID` on the network | Make each board unique |
| Publishes but no data in DB | Payload key mismatch or device not registered | Check `docs/mqtt-topics.md`, insert into `devices` |
| Wrong readings | Wrong pin or missing pull-up | Verify against `#define` pins and wiring table |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)