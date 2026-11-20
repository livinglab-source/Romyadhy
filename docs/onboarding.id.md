# Onboarding (Clone → Jalan)

[English](onboarding.md) | [Bahasa Indonesia](onboarding.id.md)

Untuk kontributor baru. Ikuti berurutan; jangan lewati pengecekan.

## 0. Yang dibutuhkan

| Item | Catatan |
|---|---|
| Linux / macOS / WSL | Windows: gunakan WSL, bukan CMD native |
| Python 3.11+ | `python3 --version` |
| Git | |
| Akses WiFi lab (2.4 GHz) | Untuk device nyata |
| Nilai `.env` | Tanya admin lab — tidak ada di git |

Opsional untuk firmware: PlatformIO Core (`pip install platformio`) atau VS Code + ekstensi PlatformIO.

## 1. Ambil kode

```bash
git clone <repo-url> Romyadhy
cd Romyadhy
```

## 2. Baca berurutan (15 menit)

1. [README.id.md](../README.id.md) — sistem ini apa
2. [architecture.id.md](architecture.id.md) — bagaimana bagian-bagiannya berkomunikasi
3. [mqtt-topics.id.md](mqtt-topics.id.md) — kontraknya
4. README komponen yang akan Anda sentuh

## 3. Konfigurasi

```bash
cp .env.example .env
# edit .env: MQTT_HOST, DB_*, TELEGRAM_BOT_TOKEN
```

Jangan pernah commit `.env`. Pastikan sudah diabaikan:

```bash
git check-ignore -v .env    # harus mencetak .gitignore:<baris>:.env
```

## 4. Broker dan database

Proyek ini tidak memakai Docker. Dua kasus:

**A — Anda bekerja di Pi (kasus normal):** Mosquitto dan MariaDB sudah terpasang dan berjalan. Set `MQTT_HOST=127.0.0.1` dan `DB_HOST=127.0.0.1` di `.env`, lalu lanjut ke §5.

**B — Anda mengembangkan di mesin sendiri:** pasang dan jalankan secara lokal.

```bash
sudo apt install mosquitto mosquitto-clients mariadb-server
sudo systemctl start mosquitto mariadb
mysql -u root -p < db/schema.sql
```

## 5. Layanan Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/data-logger/requirements.txt
pip install -r services/telegram-bot/requirements.txt

scripts/run_services.sh
```

## 6. Firmware (hanya jika punya board)

Sketch firmware (`.ino`) dapat di-flash lewat Arduino IDE atau PlatformIO:

- **Node Sensor ESP32:** `firmware/esp32-sensor-node/keren-12.ino`
- **Kontroler Relay ESP32:** `firmware/esp32-relay/ESP32-RELAY.ino`
- **Wemos Level Air A:** `firmware/wemos-gateway/wemos_a_waterlevel_code.ino`
- **Wemos Level Air B:** `firmware/wemos-gateway/wemos_b_waterlevel_code.ino`

Atur kredensial WiFi (`ssid`, `password`) dan IP broker MQTT (`mqtt_server`) di bagian atas masing-masing sketch sebelum flashing.

## 7. Verifikasi end to end

Jalankan di empat terminal:

```bash
# 1. Pantau MQTT
mosquitto_sub -t 'smartgreengarden/#' -v

# 2. Pantau logger
journalctl -u data-logger -f          # atau output run_services.sh

# 3. Pantau DB
watch -n 5 'mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"'

# 4. Bicara ke bot
#    kirim /status esp32-01 di Telegram
```

Sukses = pesan MQTT baru muncul **dan** jumlah baris DB bertambah **dan** bot menjawab.

## 8. Membuat perubahan pertama

```bash
git switch -c feat/perubahan-anda
# edit
git add <files>
git commit -m "feat(komponen): deskripsi singkat"
git push -u origin feat/perubahan-anda
```

Buka PR. Jangan push langsung ke `main`.

## 9. Ke mana saat macet

| Kebutuhan | Ke |
|---|---|
| Data tidak mengalir | [troubleshooting.id.md](troubleshooting.id.md) §1–§2 |
| Layanan crash | [troubleshooting.id.md](troubleshooting.id.md) §3 |
| Error DB | [troubleshooting.id.md](troubleshooting.id.md) §4 |
| Setup Pi dari nol | [deployment.id.md](deployment.id.md) |
| Bentuk payload | [mqtt-topics.id.md](mqtt-topics.id.md) |

## Checklist

- [ ] `.env` dibuat dan diabaikan git
- [ ] Broker terjangkau (`mosquitto_sub` menampilkan pesan)
- [ ] Skema diterapkan (`SELECT COUNT(*) FROM hydroponic_water_data_romy` berhasil)
- [ ] Tiga layanan start tanpa traceback
- [ ] Minimal satu reading masuk MariaDB
- [ ] Bot menjawab `/start`

TODO: tambahkan kontak admin lab dan URL repo sebenarnya.