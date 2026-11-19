# MQTT Topics (Contract)

[English](mqtt-topics.md) | [Bahasa Indonesia](mqtt-topics.id.md)

> **This document is a contract.** Firmware and Python services must agree on it.
> Renaming a topic or a payload key is a **breaking change** — update both sides and note it here.

## Root prefix

All topics start with `MQTT_TOPIC_PREFIX`, default `smartgreengarden`.

```
smartgreengarden/<path>
```

The bot and firmware build topics from this prefix, so a different one is a config change, not a code change.

> Historical note: older firmware used a separate `smartgarden/...` root for relays and mode. The current bot publishes everything under the single `smartgreengarden` prefix. If your firmware still listens on `smartgarden/relay/...`, align it — see [Legacy topics](#legacy-topics).

## Sensor data

| Topic | Direction | Payload |
|---|---|---|
| `smartgreengarden/sensor/data` | ESP32 → bot | JSON, see below |
| `smartgreengarden/sensor/request_data` | bot → ESP32 | `1` — asks for an immediate reading |
| `smartgreengarden/notification` | ESP32 → bot | `{"alert": "...", "level": "warning"}` |
| `smartgreengarden/waterlevel/wemosA` | Wemos A → bot | JSON, see below (retained) |
| `smartgreengarden/waterlevel/wemosB` | Wemos B → bot | JSON, see below (retained) |

### `sensor/data` payload

> **Key casing matters.** The firmware uses mixed casing — consumers must match exactly.

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

| Key | Unit | Range | Meaning |
|---|---|---|---|
| `tds1` | ppm | 0–2000 | TDS probe 1 (ADS1115 AIN2) |
| `tds2` | ppm | 0–2000 | TDS probe 2 (ADS1115 AIN3) |
| `turbidity` | NTU | 0–∞ | Computed as `A × voltage + B`; clamped to 0 minimum |
| `voltage_turbidity` | V | 0–4.096 | Raw ADS1115 AIN0 voltage, 3 decimal places |
| `FlowRate` | L/min | 0–∞ | Computed as `pulse_count / 7.5` per second |
| `Level1`–`Level4` | % | 0–100 | Water level, linearised from ADC with per-sensor calibration |
| `adc_level1`–`adc_level4` | raw | 0–4095 | Raw ESP32 ADC reading before linearisation |

The firmware does **not** send `delta_tds` or `water_quality` — those are computed by the bot from the raw values above. Send `"nan"` only if a probe failed; the bot replaces it with `0.0` and excludes it from statistics.

### `waterlevel/wemosA` payload

```json
{"level1": 88, "level1_cm": 3.52, "level2": 64, "level2_cm": 2.56}
```

### `waterlevel/wemosB` payload

```json
{"level3": 41, "level3_cm": 1.64, "level4": 27, "level4_cm": 1.08}
```

| Key | Unit | Range | Meaning |
|---|---|---|---|
| `level1`–`level4` | % | 0–100 | Water level percentage (linearised from ADS1115 ADC) |
| `level1_cm`–`level4_cm` | cm | 0–4.0 | Depth in cm (sensor strip = 40 mm) |

Both topics are **retained**. LWT `{"offline":true}` is set on each connection — the broker publishes it if the node dies.

### `notification` payload

```json
{ "alert": "Turbidity above 80 NTU", "level": "warning" }
```

`level` is optional; one of `critical`, `warning`, `info`, `system`. When omitted, the bot infers it: messages containing *normal*, *ok*, *success*, *info*, or *cleared* become `info`, everything else `warning`.

## Relay and mode

| Topic | Direction | Payload |
|---|---|---|
| `smartgreengarden/system/mode` | both | `auto` / `manual` |
| `smartgreengarden/relay/pompa_irigasi/command` | both | `1` / `0` |
| `smartgreengarden/relay/pengurasan_tandon/command` | both | `1` / `0` |
| `smartgreengarden/relay/pengurasan/command` | both | `1` / `0` |
| `smartgreengarden/relay/pengaduk_tandon/command` | both | `1` / `0` |
| `smartgreengarden/relay/valve_tandon/command` | both | `1` / `0` |
| `smartgreengarden/relay/pompa_kuras/command` | both | `1` / `0` |

These are **bidirectional on purpose**: the bot publishes a command, and the firmware publishes the resulting state back to the same topic. That is how the relay panel stays truthful after an automation-triggered change.

| Relay | Physical device |
|---|---|
| `pompa_irigasi` | Irrigation pump |
| `pengurasan_tandon` | Reservoir drain sequence |
| `pengurasan` | Drain/brew sequence |
| `pengaduk_tandon` | Reservoir stirrer |
| `valve_tandon` | Reservoir valve (direct) |
| `pompa_kuras` | Drain pump (direct) |

`system/mode` is also bidirectional: `/mode manual` publishes it, and the firmware echoes it so the bot shows the real state rather than what it hoped for.

## Calibration

The firmware subscribes to these topics for remote TDS calibration. Turbidity calibration is serial-only (`CALTURB`).

| Topic | Direction | Payload |
|---|---|---|
| `smartgreengarden/sensor/kalibrasi/tds1` | bot → ESP32 | `<ppm>` (single-point, e.g. `342`) |
| `smartgreengarden/sensor/kalibrasi/tds2` | bot → ESP32 | `<ppm>` (single-point) |

Valid range: TDS 0–5000 ppm. The firmware adjusts the K-value and saves it to EEPROM.

> `kalibrasi` spelling (Indonesian) is what the firmware uses. Do not rename without updating the firmware at the same time.

## Legacy topics

Older firmware revisions used a `smartgarden/` root and a few different paths:

| Legacy | Current |
|---|---|
| `smartgarden/relay/pompa_irigasi/command` | `smartgreengarden/relay/pompa_irigasi/command` |
| `smartgarden/system/mode` | `smartgreengarden/system/mode` |

If relays answer the bot but the dashboard does not (or vice versa), this mismatch is the first thing to check: `mosquitto_sub -t 'smartgarden/#' -v` versus `-t 'smartgreengarden/#'`.

## Debugging

```bash
# Everything
mosquitto_sub -t 'smartgreengarden/#' -v

# Both roots, to catch legacy firmware
mosquitto_sub -t 'smartgarden/#' -t 'smartgreengarden/#' -v

# Sensor data only
mosquitto_sub -t 'smartgreengarden/sensor/data' -v

# Alerts only
mosquitto_sub -t 'smartgreengarden/notification' -v

# Fire a manual relay command (bypasses the bot)
mosquitto_pub -t 'smartgreengarden/relay/pompa_irigasi/command' -m '1'

# Ask the ESP32 for a fresh reading
mosquitto_pub -t 'smartgreengarden/sensor/request_data' -m '1'
```

## Rules

- No leading slash — `/smartgreengarden/...` is a different tree.
- One root prefix. Do not add a second one for a new feature.
- Relay topics are bidirectional; do not break the echo.
- Any change to a payload key is breaking: update `services/telegram-bot/telegrambot.py`, the firmware, and this file in the same commit.