# Wemos Gateway — Water Level Nodes

[English](README.md) | [Bahasa Indonesia](README.id.md)

Two Wemos D1 Mini boards (A and B), each reading 2 water-level sensors via an ADS1115 and publishing to MQTT every 30 seconds.

| Node | Sketch | MQTT client id | Topic | Sensors |
|---|---|---|---|---|
| Wemos A | `wemos_a_waterlevel_code.ino` | `WEMOS_A` | `smartgreengarden/waterlevel/wemosA` | Level 1 & 2 |
| Wemos B | `wemos_b_waterlevel_code.ino` | `WEMOS_B` | `smartgreengarden/waterlevel/wemosB` | Level 3 & 4 |

## Responsibilities

- Power-gate each sensor individually (D5 / D6) to reduce corrosion
- Average 50 ADS1115 readings per measurement cycle
- Apply per-sensor linear calibration (adc_min → 0 %, adc_max → 100 %)
- Apply a deadband (10 % of range from adc_min) to suppress near-empty noise
- Publish level % and cm values to MQTT (retained); register LWT `{"offline":true}`
- Auto-reconnect WiFi (every 10 s) and MQTT (every 5 s) without blocking

## Hardware

Both nodes are identical hardware — only calibration values and MQTT client/topic differ.

| Component | Model | Notes |
|---|---|---|
| MCU | Wemos D1 mini (ESP8266) | 2.4 GHz WiFi only |
| ADC expander | ADS1115 | I²C address 0x48, GAIN_ONE (±4.096 V) |
| Level sensor A/B | Resistive analog (×2 per node) | Power-gated via GPIO |

Wiring: [../../docs/hardware.md](../../docs/hardware.md#wiring--wemos-a--b-water-level-nodes)

## Configuration

Credentials are hard-coded in each sketch. Update before flashing:

| Constant | Wemos A | Wemos B |
|---|---|---|
| `ssid` | `LivingLab` | `LivingLab` |
| `password` | (see sketch) | (see sketch) |
| `mqtt_server` | `192.168.88.88` | `192.168.88.88` |
| `mqtt_client_id` | `WEMOS_A` | `WEMOS_B` |
| `mqtt_topic` | `smartgreengarden/waterlevel/wemosA` | `smartgreengarden/waterlevel/wemosB` |
| `PUBLISH_INTERVAL_MS` | 30000 | 30000 |

## MQTT

Contract: [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md)

### Wemos A — `smartgreengarden/waterlevel/wemosA`

```json
{"level1": 88, "level1_cm": 3.52, "level2": 64, "level2_cm": 2.56}
```

### Wemos B — `smartgreengarden/waterlevel/wemosB`

```json
{"level3": 41, "level3_cm": 1.64, "level4": 27, "level4_cm": 1.08}
```

Both topics are published **retained**. LWT `{"offline":true}` is registered on each connection.

## Calibration

Each sensor requires a dry + wet calibration run. The firmware has a built-in guided mode.

### Step-by-step

**Step 1 — Dry calibration (adc_min)**
1. Keep both sensors completely dry
2. Set `CAL_MODE_DRY true`, `CAL_MODE_WET false` in the sketch
3. Flash → open Serial Monitor at 115200 baud
4. Copy the printed `adc_min` suggestions into `calS1`/`calS2` (or `calS3`/`calS4`)
5. Set `CAL_MODE_DRY false`

**Step 2 — Wet calibration (adc_max)**
1. Submerge both sensors to maximum expected depth in your actual nutrient solution
2. Set `CAL_MODE_WET true`, `CAL_MODE_DRY false`
3. Flash → open Serial Monitor
4. Copy the printed `adc_max` suggestions into the struct
5. Set `CAL_MODE_WET false`

**Step 3 — Normal operation**
Both flags `false` → flash → device runs normally.

### Current calibration values

| Node | Sensor | `adc_min` | `adc_max` | `sensor_len_mm` |
|---|---|---|---|---|
| Wemos A | S1 (Ch0) | 4941 | 7246 | 40.0 |
| Wemos A | S2 (Ch1) | 4015 | 32767 | 40.0 |
| Wemos B | S3 (Ch0) | 2250 | 6450 | 40.0 |
| Wemos B | S4 (Ch1) | 1007 | 5500 | 40.0 |

> `adc_max = 32767` on S2 means wet calibration has not been done yet for that sensor.

### Noise diagnosis (printed during calibration)

| Spread | Verdict |
|---|---|
| < 50 | STABLE — trust the result |
| 50–150 | MODERATE — minor noise, acceptable |
| > 150 | HIGH NOISE — check GND and sensor traces |

## Build and flash

```bash
# Arduino IDE — open the .ino, select "LOLIN(Wemos) D1 R2 & mini", flash
# or PlatformIO:
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| LED blinks fast at boot | ADS1115 not found | Check I²C wiring (SDA=D2, SCL=D1, ADDR=GND→0x48) |
| WiFi never connects | Wrong SSID / 5 GHz network | Update `ssid`/`password`; use 2.4 GHz |
| MQTT keeps reconnecting | IP wrong or broker down | Verify `mqtt_server`; `ping 192.168.88.88` |
| Level always 0 | Deadband trigger / dry calibration off | Re-run dry calibration; check ADS1115 channel wiring |
| Level always 100 | adc_max too low / wet cal needed | Re-run wet calibration |
| Readings jittery | High noise spread during calibration | Check sensor GND and power-gate pin wiring |
| Duplicate client id error | Two nodes with same `mqtt_client_id` | Confirm A uses `WEMOS_A` and B uses `WEMOS_B` |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)
