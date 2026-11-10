# Hardware

[English](hardware.md) | [Bahasa Indonesia](hardware.id.md)

> Folder names describe **roles**. This table maps each role to the actual board.

## Board → role mapping

| Role | Board | Folder | Device id (MQTT) |
|---|---|---|---|
| Sensor node | ESP32 (TODO: exact model, e.g. DevKit V1) | `firmware/esp32-sensor-node` | `esp32-01` |
| Gateway / relay | Wemos D1 mini (ESP8266) | `firmware/wemos-gateway` | `wemos-01` |
| Broker + services | Raspberry Pi (TODO: model / RAM / OS) | `services/`, `deploy/` | — |

TODO: confirm the roles. If the ESP32 is the gateway and the Wemos is the sensor node, swap the rows above and rename the folders accordingly.

## Bill of materials

| Qty | Item | Notes |
|---|---|---|
| 1 | ESP32 development board | TODO: exact variant |
| 1 | Wemos D1 mini | ESP8266-based |
| 1 | Raspberry Pi | Broker, database, Python services |
| TODO | Temperature/humidity sensor | TODO: DHT22 / BME280 / other |
| TODO | Power supply | TODO: voltage, current |
| TODO | Jumper wires, breadboard | |

## Wiring — ESP32 sensor node

| Sensor pin | ESP32 pin | GPIO | Notes |
|---|---|---|---|
| VCC | 3V3 | — | TODO: check sensor voltage (3.3 V vs 5 V) |
| GND | GND | — | |
| DATA | TODO | TODO | TODO: pull-up resistor if required |

## Wiring — Wemos gateway

| Function | Wemos pin | GPIO | Notes |
|---|---|---|---|
| TODO | TODO | TODO | TODO |

> Keep this table in sync with the pin `#define`s in `firmware/*/src/main.cpp`. A mismatch here is the most common "it worked yesterday" bug.

## Power

| Board | Supply | Typical draw | Notes |
|---|---|---|---|
| ESP32 | TODO | TODO | WiFi bursts can spike current |
| Wemos D1 mini | TODO | TODO | |
| Raspberry Pi | TODO | TODO | Use a proper PSU; undervoltage causes random reboots |

## Network

| Item | Value |
|---|---|
| WiFi band | 2.4 GHz only (ESP32/ESP8266 do not support 5 GHz) |
| Broker host | Raspberry Pi LAN IP — TODO |
| Broker port | `1883` (no TLS) / `8883` (TLS) |
| DHCP reservation | Recommended, so the broker IP is stable |

## Photos and diagrams

Store images in [`images/`](images/) and reference them here:

```markdown
![Wiring](images/esp32-wiring.jpg)
```

TODO: add wiring photo and a labelled board photo.