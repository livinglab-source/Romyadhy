# Hardware

[English](hardware.md) | [Bahasa Indonesia](hardware.id.md)

> Folder names describe **roles**. This table maps each role to the actual board.

## Board → role mapping

| Role | Board | Folder | Device id (MQTT) |
|---|---|---|---|
| Sensor node | ESP32 DevKit (WROOM-32) | `firmware/esp32-sensor-node` | `ESP32_SENSOR` |
| Relay controller | ESP32 DevKit (WROOM-32) | `firmware/esp32-relay` | `ESP32_Hidroponik_Client` |
| Water-level node A | Wemos D1 mini (ESP8266) | `firmware/wemos-gateway` (`wemos_a_*`) | `WEMOS_A` |
| Water-level node B | Wemos D1 mini (ESP8266) | `firmware/wemos-gateway` (`wemos_b_*`) | `WEMOS_B` |
| Broker + services | Raspberry Pi | `services/`, `deploy/` | — |

## Bill of materials

| Qty | Item | Notes |
|---|---|---|
| 2 | ESP32 DevKit (WROOM-32) | 1× Sensor node, 1× Relay controller |
| 2 | Wemos D1 mini (ESP8266) | Water-level nodes (A & B) |
| 1 | 5-channel relay module / board | 2× AC relays (pump, stirrer), 3× DC relays (draining pump, 2× valves) |
| 1 | ADS1115 16-bit ADC | I²C, address 0x48, for TDS + turbidity on sensor node |
| 2 | ADS1115 16-bit ADC | 1× per Wemos water-level node |
| 2 | Gravity TDS probe | DFRobot or compatible |
| 1 | Turbidity sensor (analog) | 0–5 V output, read via ADS1115 AIN0 |
| 1 | Flow sensor YF-S201 (or equiv.) | Pulse output, 7.5 pulses per litre |
| 8 | Resistive water-level sensor | 4 on ESP32 sensor node, 2 on Wemos A, 2 on Wemos B |
| 1 | 16×2 I²C LCD | Address 0x27 |
| 1 | Raspberry Pi | MQTT broker, database, Python services |
| 2 | 5 V power supply | ≥ 2 A recommended per MCU board |

## Wiring — ESP32 sensor node

### ADS1115 (I²C)

| ADS1115 pin | ESP32 pin | Notes |
|---|---|---|
| VDD | 3V3 | — |
| GND | GND | — |
| SCL | GPIO 22 | Standard ESP32 I²C clock |
| SDA | GPIO 21 | Standard ESP32 I²C data |
| ADDR | GND | Sets I²C address to 0x48 |
| AIN0 | Turbidity sensor output | Via voltage divider if sensor outputs > 3.3 V |
| AIN2 | TDS probe 1 output | — |
| AIN3 | TDS probe 2 output | — |

### Level sensors

| Signal | ESP32 GPIO | Notes |
|---|---|---|
| Level 1 analog | GPIO 32 | ADC1_CH4 |
| Level 2 analog | GPIO 33 | ADC1_CH5 |
| Level 3 analog | GPIO 34 | ADC1_CH6, input-only |
| Level 4 analog | GPIO 35 | ADC1_CH7, input-only |
| VCC (all 4) | GPIO 26 | Switched HIGH only during reading to reduce corrosion |

### Flow sensor

| Signal | ESP32 GPIO | Notes |
|---|---|---|
| Signal (yellow) | GPIO 27 | `INPUT_PULLUP`, interrupt on RISING |
| VCC (red) | 5 V | — |
| GND (black) | GND | — |

### LCD (I²C, shares bus with ADS1115)

| LCD pin | ESP32 pin |
|---|---|
| VCC | 5 V |
| GND | GND |
| SCL | GPIO 22 |
| SDA | GPIO 21 |

> Keep this table in sync with the `#define` / `const` pin assignments in `firmware/esp32-sensor-node/keren-12.ino`.

## Wiring — ESP32 relay controller

All outputs use **active-LOW** logic (`LOW` = ON, `HIGH` = OFF). Default state on boot is `HIGH` (all OFF).

| Actuator | Relay Type | ESP32 GPIO | Logic | Function |
|---|---|---|---|---|
| Pompa Irigasi | AC 220V | GPIO 26 | Active LOW | Main irrigation circulation |
| Pengaduk Tandon | AC 220V | GPIO 25 | Active LOW | Dinamo mixer for nutrient tank |
| Pompa Kuras | DC 12V | GPIO 27 | Active LOW | DC drainage pump |
| Valve Kuras | DC 12V | GPIO 13 | Active LOW | Drain-out solenoid valve |
| Valve Tandon | DC 12V | GPIO 32 | Active LOW | Reservoir selector valve |

> Keep this table in sync with `firmware/esp32-relay/ESP32-RELAY.ino`.

## Wiring — Wemos A & B (Water Level Nodes)

Both nodes are electrically identical. Flash the matching sketch (`wemos_a_*` or `wemos_b_*`) to set the MQTT identity.

### ADS1115 (I²C — shared by both Wemos nodes)

| ADS1115 pin | Wemos pin | GPIO | Notes |
|---|---|---|---|
| VDD | 3V3 | — | — |
| GND | GND | — | — |
| SCL | D1 | GPIO 5 | — |
| SDA | D2 | GPIO 4 | — |
| ADDR | GND | — | Sets I²C address to 0x48 |
| AIN0 | — | — | Sensor 1 (Wemos A) / Sensor 3 (Wemos B) |
| AIN1 | — | — | Sensor 2 (Wemos A) / Sensor 4 (Wemos B) |

### Level sensor power gating

| Signal | Wemos pin | GPIO | Sensor |
|---|---|---|---|
| Sensor VCC (first) | D5 | GPIO 14 | S1 on A / S3 on B |
| Sensor VCC (second) | D6 | GPIO 12 | S2 on A / S4 on B |

> Sensor GND → Wemos GND. Sensor OUT → ADS1115 AINx (see above).

## Power

| Board | Supply | Notes |
|---|---|---|
| ESP32 | 5 V via USB or VIN | WiFi bursts can spike current; use ≥ 2 A supply |
| Wemos D1 mini | 5 V via USB or 5 V pin | — |
| Raspberry Pi | 5 V / 3 A (official PSU) | Undervoltage causes random reboots |

## Network

| Item | Value |
|---|---|
| WiFi SSID | `SGG X FSR` (2.4 GHz) |
| WiFi band | 2.4 GHz only (ESP32/ESP8266 do not support 5 GHz) |
| Broker host | `192.168.88.88` (Raspberry Pi, static/reserved) |
| Broker port | `1883` (no TLS) |
| DHCP reservation | Required — broker IP is hard-coded in firmware |

## Photos and diagrams

Store images in [`images/`](images/) and reference them here:

```markdown
![Wiring](images/esp32-wiring.jpg)
```

TODO: add wiring photo and a labelled board photo.
