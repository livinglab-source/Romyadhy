# ESP32 Relay Controller

[English](README.md) | [Bahasa Indonesia](README.id.md)

Controls AC and DC relays for irrigation pumps, nutrient stirrers, drainage pumps, and motorized valves based on MQTT commands.

- Role: actuator / relay node
- Board: ESP32 DevKit (WROOM-32)
- MQTT client id: `ESP32_Hidroponik_Client`

## Responsibilities

- Control 5 actuators: irrigation pump, stirrer motor, drainage pump, drain-out valve, reservoir valve
- Execute timed interlock sequences for drainage (`kuras_tandon` and `kuras`)
- Direct ON/OFF switching for irrigation and stirrer
- Failsafe boot state: all relays forced OFF (`HIGH`) immediately on power-up
- Hardware watchdog timer (`esp_task_wdt`) with 10-second timeout
- Auto-reconnect to WiFi (auto-restarts after 15 s timeout) and MQTT (retries every 5 s)

## Hardware & Pinout

All relay outputs use **active-LOW logic**:
- `digitalWrite(pin, LOW)` = **ON**
- `digitalWrite(pin, HIGH)` = **OFF** (boot default)

| Actuator | Type | GPIO | Logic | Description |
|---|---|---|---|---|
| Pompa Irigasi | AC | GPIO 26 | Active LOW | Main irrigation pump |
| Pengaduk Tandon | AC | GPIO 25 | Active LOW | Nutrient mixer / stirrer motor |
| Pompa Kuras | DC | GPIO 27 | Active LOW | DC drainage pump |
| Valve Kuras | DC | GPIO 13 | Active LOW | Drain-out solenoid/valve |
| Valve Tandon | DC | GPIO 32 | Active LOW | Reservoir selector valve |

Wiring table: [../../docs/hardware.md](../../docs/hardware.md#wiring--esp32-relay-controller)

## MQTT Subscriptions

The controller listens to the following command topics:

| Topic | Payload | Controlled Actuator / Sequence |
|---|---|---|
| `smartgarden/relay/pompa_irigasi/command` | `1` / `0` | Direct ON/OFF: Pompa Irigasi (GPIO 26) |
| `smartgarden/relay/pengaduk_tandon/command` | `1` / `0` | Direct ON/OFF: Pengaduk Tandon (GPIO 25) |
| `smartgarden/relay/valve_tandon/command` | `1` / `0` | Direct ON/OFF: Valve Tandon (GPIO 32) |
| `smartgarden/relay/pompa_kuras/command` | `1` / `0` | Direct ON/OFF: Pompa Kuras DC (GPIO 27) |
| `smartgarden/relay/pengurasan_tandon/command` | `1` / `0` | Timed Sequence: Reservoir drainage (see below) |
| `smartgarden/relay/pengurasan/command` | `1` / `0` | Timed Sequence: System drain out (see below) |

> **Topic Prefix Notice:** The sketch currently listens on `smartgarden/relay/...`. The default Telegram bot prefix is `smartgreengarden`. If controlling via the bot, verify the bot's `MQTT_TOPIC_PREFIX` in `.env` matches the firmware or align the sketch's topic constants. See [../../docs/mqtt-topics.md](../../docs/mqtt-topics.md#legacy-topics).

## Drainage Sequences (Interlock)

To prevent pump cavitation or pressure buildup against closed valves, the controller enforces timed sequences:

### 1. Pengurasan Tandon (`smartgarden/relay/pengurasan_tandon/command`)
- **START (`1`):**
  1. Closes Valve Drain Out (`GPIO 13` -> OFF)
  2. Opens Valve Tandon (`GPIO 32` -> ON)
  3. Waits **500 ms** (`delayTurnOn`) for valve to physically open
  4. Starts Draining Pump DC (`GPIO 27` -> ON)
- **STOP (`0`):**
  1. Closes Valve Tandon (`GPIO 32` -> OFF)
  2. Waits **1500 ms** (`delayTurnOff`) to clear remaining water
  3. Stops Draining Pump DC (`GPIO 27` -> OFF)

### 2. Pengurasan / Drain Out (`smartgarden/relay/pengurasan/command`)
- **START (`1`):**
  1. Closes Valve Tandon (`GPIO 32` -> OFF)
  2. Opens Valve Drain Out (`GPIO 13` -> ON)
  3. Waits **500 ms** (`delayTurnOn`)
  4. Starts Draining Pump DC (`GPIO 27` -> ON)
- **STOP (`0`):**
  1. Closes Valve Drain Out (`GPIO 13` -> OFF)
  2. Waits **1500 ms** (`delayTurnOff`)
  3. Stops Draining Pump DC (`GPIO 27` -> OFF)

## Configuration

Credentials are set at the top of `ESP32-RELAY.ino`:

| Constant | Default Value | Notes |
|---|---|---|
| `ssid` | `"LivingLab"` | 2.4 GHz WiFi |
| `password` | `"LABTengah2026!"` | Lab WiFi password |
| `mqtt_server` | `"192.168.88.88"` | Raspberry Pi broker IP |
| `mqtt_port` | `1883` | Mosquitto port |

## Safety & Watchdog

- **Watchdog:** Uses ESP32 Hardware Task Watchdog (`esp_task_wdt`) configured for 10 seconds. The loop resets the watchdog on each iteration. If the firmware hangs, the ESP32 automatically reboots.
- **WiFi Guard:** If WiFi fails to connect within 15 seconds at boot, the ESP32 automatically reboots (`ESP.restart()`).
- **Relay State at Boot:** All 5 output pins are initialized `OUTPUT` and immediately set `HIGH` before network connection to prevent relay chatter or inadvertent pump activation during boot.

## Build and Flash

```bash
# Arduino IDE:
# 1. Open firmware/esp32-relay/ESP32-RELAY.ino
# 2. Select Board: "ESP32 Dev Module"
# 3. Select Port and Upload
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Relays turn on at boot | Active LOW inversion | Pins must be initialized `HIGH`. Check `setup()` |
| Relays do not switch on MQTT | Wrong topic prefix | Check if bot sends `smartgreengarden/` vs `smartgarden/` |
| Pump turns on without valve | Sequence bypassed | Send command to `pengurasan_tandon` or `pengurasan`, not raw pins |
| ESP32 reboots continuously | Watchdog trigger / WiFi failure | Check serial monitor at 115200 baud; verify WiFi credentials |

More: [../../docs/troubleshooting.md](../../docs/troubleshooting.md)
