# ESP32 Sensor Node

[English](README.md) | [Bahasa Indonesia](README.id.md)

Reads water-quality sensors and publishes readings to MQTT every `sensorInterval` (5 s).

- Role: sensor node
- Board: ESP32 (DevKit / WROOM-32)
- MQTT client id: `ESP32_SENSOR`

## Responsibilities

- Read 2× TDS probes, 1× turbidity sensor, 1× flow meter, 4× water-level sensors
- Publish `smartgreengarden/sensor/data` every 5 seconds
- Subscribe to `smartgreengarden/sensor/kalibrasi/tds1` and `tds2` for MQTT-triggered calibration
- Accept serial commands (`CALTDS1 <ppm>`, `CALTDS2 <ppm>`, `CALTURB`) for bench calibration

## Hardware

| Component | Model | Notes |
|---|---|---|
| MCU | ESP32 DevKit (WROOM-32) | 2.4 GHz WiFi only |
| ADC expander | ADS1115 | I²C, address 0x48, gain GAIN_ONE (±4.096 V) |
| TDS probe 1 | Gravity TDS | ADS1115 AIN2 |
| TDS probe 2 | Gravity TDS | ADS1115 AIN3 |
| Turbidity sensor | Analog voltage | ADS1115 AIN0 |
| Flow sensor | YF-S201 (or equivalent) | GPIO 27, interrupt on RISING edge |
| Water-level 1–4 | Resistive analog | GPIO 32, 33, 34, 35 (ADC) |
| Level sensor VCC | — | GPIO 26 (power switched to avoid continuous heating) |
| LCD | 16×2 I²C | Address 0x27 |

Wiring table: [../../docs/hardware.md](../../docs/hardware.md#wiring--esp32-sensor-node)

## Configuration

Credentials are hard-coded in the sketch (not committed via config.h). Update these constants before flashing:

| Constant | Location | Meaning |
|---|---|---|
| `ssid` / `password` | top of `.ino` | Lab WiFi (2.4 GHz) |
| `mqtt_server` | top of `.ino` | Raspberry Pi LAN IP (`192.168.88.88`) |
| `mqtt_port` | top of `.ino` | `1883` |
| `mqtt_client_id` | top of `.ino` | `ESP32_SENSOR` |

EEPROM layout (512 bytes):

| Address | Content |
|---|---|
| 0 | TDS1 K-value (`float`, 4 bytes) |
| 10 | TDS2 K-value (`float`, 4 bytes) |
| 20 | Turbidity slope A (`float`, 4 bytes) |
| 24 | Turbidity intercept B (`float`, 4 bytes) |

## MQTT

Contract: [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md)

| Direction | Topic | Payload |
|---|---|---|
| publish | `smartgreengarden/sensor/data` | JSON — see below |
| subscribe | `smartgreengarden/sensor/kalibrasi/tds1` | `<ppm>` — single-point calibration |
| subscribe | `smartgreengarden/sensor/kalibrasi/tds2` | `<ppm>` — single-point calibration |

### `sensor/data` payload (actual keys from firmware)

```json
{
  "tds1": 812.45,
  "tds2": 795.10,
  "turbidity": 12.50,
  "voltage_turbidity": 1.234,
  "FlowRate": 6.20,
  "Level1": 88,
  "adc_level1": 650,
  "Level2": 64,
  "adc_level2": 340,
  "Level3": 41,
  "adc_level3": 480,
  "Level4": 27,
  "adc_level4": 420
}
```

> **Note:** Key casing is mixed (`FlowRate`, `Level1`–`Level4` use capitals; others are lowercase). Consumers must match exactly.

## Timers

| Variable | Interval | What happens |
|---|---|---|
| `sensorInterval` | 5 000 ms | Read TDS, turbidity; publish MQTT |
| `waterLevelInterval` | 60 000 ms | Read all 4 water-level sensors |
| `displayInterval` | 3 000 ms | Rotate LCD to next screen (7 screens total) |
| Flow calc | 1 000 ms | Compute L/min from pulse count, then reset counter |

## Calibration

### Via Serial Monitor (115200 baud)

| Command | Action |
|---|---|
| `CALTDS1 <ppm>` | Single-point TDS1 calibration. Adjusts K-value, saves to EEPROM. |
| `CALTDS2 <ppm>` | Single-point TDS2 calibration. Adjusts K-value, saves to EEPROM. |
| `CALTURB` | Interactive 2-point turbidity calibration (0 NTU then 50 NTU). Saves A/B to EEPROM. |

### Via MQTT

Publish `<ppm>` to `smartgreengarden/sensor/kalibrasi/tds1` or `tds2`.

### Water-level linear calibration

Calibration constants are hard-coded in `linear_calibrations[]`. Edit the array and re-flash to change them.

| Sensor | ADC min (0 %) | ADC max (100 %) |
|---|---|---|
| Level 1 | 300 | 687 |
| Level 2 | 200 | 422 |
| Level 3 | 100 | 949 |
| Level 4 | 300 | 717 |

## Build and flash

```bash
# Arduino IDE — open keren-12.ino, select ESP32 Dev Module, flash
# or PlatformIO:
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Boot loop / `ADS1115 Error!` on LCD | ADS1115 not detected on I²C | Check wiring and I²C address (0x48) |
| WiFi never connects | 5 GHz network or wrong credentials | Use 2.4 GHz; update `ssid`/`password` in sketch |
| MQTT keeps reconnecting | Broker IP wrong or broker down | Check `mqtt_server`; `ping 192.168.88.88` |
| TDS reads 0 or garbage | K-value lost or probe disconnected | Send `CALTDS1 <known_ppm>` or check ADS1115 AIN2/3 |
| Turbidity always 0 or negative | Calibration not done | Send `CALTURB` via Serial Monitor |
| Water level stuck / wrong | ADC calibration mismatch | Update `linear_calibrations[]` and re-flash |
| Flow always 0 | Interrupt not firing | Check GPIO 27 wiring; verify `INPUT_PULLUP` |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)
