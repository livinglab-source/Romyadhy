# Romyadhy Projects Documentation Living Lab

**Smart Green Garden:** node hidroponik ESP32 → MQTT (Mosquitto) → layanan Raspberry Pi → MariaDB + Telegram.

[English](README.md) | [Bahasa Indonesia](README.id.md)

> Terjemahan ini mengikuti versi Inggris (`README.md`). Jika ada perbedaan, versi Inggris yang dianggap benar.

---

## Arsitektur

```mermaid
flowchart LR
  A["ESP32<br/>sensor + relay"] -->|"sensor/data<br/>notification"| B["Broker Mosquitto<br/>(Raspberry Pi)"]
  B --> L["data-logger<br/>dataSave.py"]
  L --> DB[("MariaDB")]
  L -.->|opsional| FB[("Firebase RTDB")]
  B --> C["telegram-bot"]
  C -->|"sendMessage"| D["Telegram"]
  D -->|"/perintah"| C
  C --> E[("MariaDB")]
  C -->|"relay/*/command<br/>system/mode"| B
  B --> A
```

Penjelasan lengkap: [docs/architecture.id.md](docs/architecture.id.md)

---

## Komponen

| Komponen | Folder | Bahasa | Status | Dokumentasi |
|---|---|---|---|---|
| Node hidroponik ESP32 | `firmware/esp32-sensor-node` | C++ (Arduino IDE) | ✅ sudah ada | [README](firmware/esp32-sensor-node/README.md) |
| Node level air Wemos (A & B) | `firmware/wemos-gateway` | C++ (Arduino IDE) | ✅ sudah ada | [README](firmware/wemos-gateway/README.md) |
| Data logger | `services/data-logger` | Python 3.11 | ✅ sudah ada | [README](services/data-logger/README.md) |
| Telegram bot | `services/telegram-bot` | Python 3.11 | ✅ sudah ada | [README](services/telegram-bot/README.md) |

> Nama folder menunjukkan **peran**, bukan tipe board. Pemetaan board → peran: [docs/hardware.md](docs/hardware.md)

---

## Mulai cepat

```bash
git clone <repo-url> && cd Romyadhy
cp .env.example .env          # lalu isi kredensial MQTT, DB, Telegram, ACCESS_PASSWORD
mysql -u root -p < db/schema.sql
scripts/run_services.sh       # menjalankan layanan yang sudah ada
```

Di Raspberry Pi, Mosquitto dan MariaDB sudah terpasang — hanya `.env` dan skema yang perlu disiapkan. Tidak ada Docker di mana pun.

Cek data mengalir:

```bash
mosquitto_sub -t 'smartgreengarden/#' -v
```

Panduan lengkap Raspberry Pi (systemd, autostart, backup): [docs/deployment.id.md](docs/deployment.id.md)

---

## Perangkat keras (ringkasan)

| Board | Peran | Komponen utama | Dokumentasi |
|---|---|---|---|
| ESP32 (WROOM-32) | Node sensor | ADS1115, 2× probe TDS, turbiditas, flow meter, 4× sensor level, LCD 16×2 | [docs/hardware.md](docs/hardware.md) |
| Wemos D1 mini × 2 (A & B) | Node level air | ADS1115, 2× sensor level resistif per node | [docs/hardware.md](docs/hardware.md) |
| Raspberry Pi | Broker + layanan + DB | — | [docs/deployment.id.md](docs/deployment.id.md) |

---

## Dokumentasi

| Dokumen | Isi |
|---|---|
| [architecture.id.md](docs/architecture.id.md) | Alur data end-to-end, tanggung jawab tiap layanan |
| [hardware.md](docs/hardware.md) | BOM, wiring, tabel pinout, pemetaan board → peran |
| [mqtt-topics.id.md](docs/mqtt-topics.id.md) | **Kontrak topik + payload** antara firmware dan Python |
| [database.md](docs/database.md) | Skema MariaDB, diagram ER, retensi, backup |
| [telegram-bot.md](docs/telegram-bot.md) | Perintah, setup token, chat id yang diizinkan |
| [deployment.id.md](docs/deployment.id.md) | Setup Pi: Mosquitto, MariaDB, venv, systemd |
| [troubleshooting.id.md](docs/troubleshooting.id.md) | Masalah umum dan cara mendiagnosis |
| [onboarding.id.md](docs/onboarding.id.md) | Checklist "clone → jalan" untuk kontributor baru |

---

## Status proyek

- [x] Struktur repositori dan dokumentasi
- [x] Implementasi data logger (`services/data-logger/dataSave.py`)
- [x] Implementasi Telegram bot (`services/telegram-bot/telegrambot.py`)
- [x] Source firmware dimasukkan (`firmware/esp32-sensor-node`, `firmware/wemos-gateway`)
- [ ] Demo end-to-end terverifikasi

---

## Keamanan

Rahasia hanya ada di `.env` (diabaikan git). Jika token atau password pernah ter-commit, ganti sebelum dipublikasikan: lihat [docs/telegram-bot.id.md](docs/telegram-bot.id.md#catatan-keamanan).

---

## Lisensi

TODO: pilih lisensi (MIT umum dipakai untuk proyek lab) dan tambahkan file `LICENSE`.