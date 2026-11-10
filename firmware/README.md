# Firmware

[English](README.md) | [Bahasa Indonesia](README.id.md)

Each folder is one physical board. Folder names describe the **role**; the actual board model is recorded in [../docs/hardware.md](../docs/hardware.md).

| Folder | Role | Board | Device id |
|---|---|---|---|
| [`esp32-sensor-node/`](esp32-sensor-node/) | Reads sensors, publishes `data` | ESP32 | `esp32-01` |
| [`wemos-gateway/`](wemos-gateway/) | TODO: gateway / relay role | Wemos D1 mini | `wemos-01` |

> TODO: confirm roles. If they are swapped, swap the folder names and update this table, `docs/hardware.md`, and the root README.

## Common conventions

| Item | Rule |
|---|---|
| Build system | PlatformIO (`platformio.ini` per folder) |
| Entry point | `src/main.cpp` |
| Secrets | WiFi credentials NOT committed — use `src/secrets.h` (git-ignored) or build flags |
| Device identity | `DEVICE_ID` must be unique and match the MQTT topic segment |
| Payload | Follow [../docs/mqtt-topics.md](../docs/mqtt-topics.md) exactly |
| Version | `FW_VERSION` string, published in `status` |

## Build and flash

```bash
cd esp32-sensor-node
pio run                  # compile only
pio run -t upload        # flash
pio device monitor -b 115200
```

If you use the Arduino IDE instead, keep the same folder name as the `.ino` sketch so the build still works. PlatformIO is preferred because pins and library versions then live in version control.

## Adding a new board

1. Create `firmware/<role>/` with `src/main.cpp`, `platformio.ini`, `README.md`.
2. Add it to the table above and to `docs/hardware.md`.
3. Register it in the DB: `INSERT INTO devices (device_id, board_type, role) VALUES (...);`
4. Publish to `livinglab/<device-id>/data` and set a Last Will on `status`.