# Services

[English](README.md) | [Bahasa Indonesia](README.id.md)

Tiga layanan Python berjalan di Raspberry Pi, ditambah helper bersama.

| Layanan | Fungsi | Entry point | Dijalankan sebagai |
|---|---|---|---|
| [`mqtt-bridge/`](mqtt-bridge/) | Subscribe semua topik, validasi dan normalisasi payload | `main.py` | `mqtt-bridge.service` |
| [`data-logger/`](data-logger/) | Menulis reading ke MariaDB | `main.py` | `data-logger.service` |
| [`telegram-bot/`](telegram-bot/) | Alert, perintah, kontrol relay, kalibrasi, export CSV | `telegrambot.py` | `telegram-bot.service` |
| [`common/`](common/) | Config loader, koneksi DB, wrapper MQTT | — | *(library, bukan service)* |

## Status

| Layanan | Kode tersedia |
|---|---|
| `telegram-bot` | ✅ sudah ada (`telegrambot.py`) |
| `mqtt-bridge` | ⬜ direncanakan — README menjelaskan perilaku yang dituju |
| `data-logger` | ⬜ direncanakan — README menjelaskan perilaku yang dituju |

## Hubungan antar layanan

```mermaid
flowchart LR
  MQ[("Mosquitto")] --> BR["mqtt-bridge"]
  BR --> LOG["data-logger"]
  LOG --> DB[("MariaDB")]
  MQ --> BOT["telegram-bot"]
  BOT --> DB
  BOT --> MQ
```

## Konvensi

| Item | Aturan |
|---|---|
| Entry point | `main.py` di tiap folder layanan (bot memakai `telegrambot.py`) |
| Dependensi | `requirements.txt` per layanan |
| Konfigurasi | Dibaca dari environment; dev lokal memuat `.env` |
| Logging | Modul `logging` ke stdout (ditangkap journald di systemd) |
| Tanpa rahasia | Jangan hardcode token atau password — bot berhenti jika ada yang hilang |

## Jalankan lokal

```bash
scripts/run_services.sh
```

## Deploy

Lihat [../docs/deployment.id.md](../docs/deployment.id.md) dan template unit di [`../deploy/systemd/`](../deploy/systemd/).

## Menambah layanan

1. Buat `services/<nama>/` berisi `main.py`, `requirements.txt`, `README.md`.
2. Pakai ulang `services/common/` untuk config dan koneksi.
3. Tambahkan unit di `deploy/systemd/` dan dokumentasikan di README root.