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

### `sensor/data` payload

```json
{
  "tds1": 812.4,
  "tds2": 795.1,
  "delta_tds": 17.3,
  "turbidity": 12.5,
  "flowrate": 6.2,
  "level1": 88,
  "level2": 64,
  "level3": 41,
  "level4": 27,
  "water_quality": "2"
}
```

| Key | Unit | Range | Meaning |
|---|---|---|---|
| `tds1` | ppm | 0–2000 | TDS probe 1 (nutrient solution) |
| `tds2` | ppm | 0–2000 | TDS probe 2 |
| `delta_tds` | % | 0–100 | Difference between the probes |
| `turbidity` | NTU | 0–100 | ≤50 clear, >50 cloudy |
| `flowrate` | L/min | 0–30 | Irrigation flow |
| `level1` | % | 0–100 | Tank 1 — main reservoir |
| `level2` | % | 0–100 | Tank 2 — mixing basin |
| `level3` | % | 0–100 | Tank 3 — nutrient buffer |
| `level4` | % | 0–100 | Tank 4 — drain/overflow |
| `water_quality` | code | 0–4 | See below |

`water_quality` codes:

| Code | Meaning |
|---|---|
| `0` | 🟡 Cloudy — nutrient suspension |
| `1` | 🟤 Cloudy — sediment |
| `2` | 🟢 Normal / clear |
| `3` | 🟠 Nutrient imbalance |
| `4` | 🔴 Water level low |

The bot recomputes this code from the raw values before display, so a stale code in the payload cannot mislead the dashboard. Send `"nan"` only if a probe failed — the bot replaces it with `0.0` and the value is excluded from statistics.

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

| Topic | Direction | Payload |
|---|---|---|
| `smartgreengarden/sensor/calibrate/tds1/multi/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/tds1/multi/set` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/kalibrasi/tds1` | bot → ESP32 | `<ppm>` (single-point) |
| `smartgreengarden/sensor/calibrate/tds2/multi/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/tds2/multi/set` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/kalibrasi/tds2` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/calibrate/turbidity/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/next` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/cancel` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/status` | ESP32 → bot | free text |

Valid ranges: TDS 0–5000 ppm. Turbidity sequence is 0 → 50 → 100 NTU, advanced with `/next`.

Note the inconsistent spelling — `kalibrasi` for single-point TDS, `calibrate` elsewhere. This is inherited from the firmware and deliberately not changed here to avoid breaking a working setup. If you rename it, change both sides in one commit.

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