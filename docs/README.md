# Documentation Index

[English](README.md) | [Bahasa Indonesia](README.id.md)

> English is the authoritative version. Indonesian translations may lag behind.
> If a translation disagrees with the English file, the English file wins.

## Start here

| # | Document | Read it when |
|---|---|---|
| 1 | [onboarding.md](onboarding.md) | You just cloned the repo and want it running |
| 2 | [architecture.md](architecture.md) | You need the big picture / data flow |
| 3 | [deployment.md](deployment.md) | You are setting up the Raspberry Pi |
| 4 | [troubleshooting.md](troubleshooting.md) | Something does not work |

> **Scope.** This repo documents the IoT pipeline: firmware, the two Python services, the MQTT contract, and the database. The Raspberry Pi also holds other project notes and code under `/home/livinglab/workspace/romy`; read those for anything not covered here.

## Reference

| Document | Contents |
|---|---|
| [hardware.md](hardware.md) | Bill of materials, wiring, pinout, board → role mapping |
| [mqtt-topics.md](mqtt-topics.md) | Topic naming, QoS/retain, JSON payload contract |
| [database.md](database.md) | MariaDB schema, ER diagram, indexes, retention, backup |
| [telegram-bot.md](telegram-bot.md) | Bot commands, token setup, allowed chat ids |

## Translations

| English | Bahasa Indonesia |
|---|---|
| [architecture.md](architecture.md) | [architecture.id.md](architecture.id.md) |
| [deployment.md](deployment.md) | [deployment.id.md](deployment.id.md) |
| [troubleshooting.md](troubleshooting.md) | [troubleshooting.id.md](troubleshooting.id.md) |
| [onboarding.md](onboarding.md) | [onboarding.id.md](onboarding.id.md) |
| [mqtt-topics.md](mqtt-topics.md) | [mqtt-topics.id.md](mqtt-topics.id.md) |

## Conventions

- Diagrams are written in **Mermaid** inside Markdown so they are versioned with the code.
- Commands are always in fenced `bash` blocks and are copy-pasteable.
- Secrets never appear in docs. Use `.env.example` for key names only.
- Every component folder has a `README.md` with the same section order.