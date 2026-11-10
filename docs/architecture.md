# Architecture

[English](architecture.md) | [Bahasa Indonesia](architecture.id.md)

## Overview

The Living Lab is an IoT pipeline with three layers:

1. **Edge** — ESP32 and Wemos boards read sensors and publish MQTT messages.
2. **Transport** — a Mosquitto broker on the Raspberry Pi receives every message.
3. **Backend** — Python services on the Pi normalize messages, persist them to MariaDB, and notify users over Telegram.

```mermaid
flowchart TB
  subgraph Edge["Edge (sensors)"]
    ESP["ESP32 sensor node"]
    WEM["Wemos D1 mini"]
  end

  subgraph Pi["Raspberry Pi"]
    MQ[("Mosquitto<br/>:1883")]
    BR["mqtt-bridge"]
    LOG["data-logger"]
    BOT["telegram-bot"]
    DB[("MariaDB<br/>:3306")]
  end

  TG["Telegram API"]

  ESP -->|"livinglab/&lt;device&gt;/data"| MQ
  WEM -->|"livinglab/&lt;device&gt;/data"| MQ
  MQ --> BR
  BR -->|"validated, normalized"| LOG
  LOG -->|"INSERT"| DB
  MQ -->|"status"| BOT
  BOT -->|"sendMessage"| TG
  TG -->|"/commands"| BOT
  BOT -->|"query"| DB
  BOT -->|"publish cmd"| MQ
  MQ -->|"livinglab/&lt;device&gt;/cmd"| ESP
```

## Responsibilities

| Component | Owns | Does **not** do |
|---|---|---|
| Firmware (ESP32 / Wemos) | Reading sensors, publishing `data` and `status`, obeying `cmd` | Direct DB access, Telegram calls |
| `mqtt-bridge` | Subscribe to all topics, validate payload, normalize units, forward to downstream | Writing to the database |
| `data-logger` | Persist readings to MariaDB, enforce schema types | React to commands |
| `telegram-bot` | User commands, alerts, DB queries, publishing commands to devices | Parsing raw sensor payloads |

Keeping these separated means you can restart or rewrite one service without touching the others.

## Message flow (a single reading)

```mermaid
sequenceDiagram
  participant E as ESP32
  participant M as Mosquitto
  participant B as mqtt-bridge
  participant L as data-logger
  participant D as MariaDB

  E->>M: PUBLISH livinglab/esp32-01/data
  M-->>B: deliver
  B->>B: validate JSON + normalize
  B->>L: forward reading
  L->>D: INSERT INTO readings
  D-->>L: ok
```

## Design decisions

| Decision | Reason |
|---|---|
| MQTT over HTTP | Low bandwidth, QoS, retain for last-known status, works well on ESP32 |
| Broker on the Pi, not in the cloud | Lab network is local; no internet dependency for logging |
| Separate bridge and logger | Validation logic changes often; the DB writer should stay stable |
| MariaDB | Relational queries for reports; already available on campus setups |
| `.env` configuration | One codebase for dev and Pi; no secrets in git |

## Known limitations

- TODO: document any single points of failure (e.g. one broker, no HA).
- TODO: note whether messages are queued if the DB is down (QoS 1 + subscriber persistence).
- TODO: note WiFi range / node placement constraints.