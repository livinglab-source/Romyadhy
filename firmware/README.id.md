# Firmware

[English](README.md) | [Bahasa Indonesia](README.id.md)

Setiap folder adalah satu board fisik. Nama folder menunjukkan **peran**; model board sebenarnya dicatat di [../docs/hardware.id.md](../docs/hardware.id.md).

| Folder | Peran | Board | Device id |
|---|---|---|---|
| [`esp32-sensor-node/`](esp32-sensor-node/) | Membaca sensor, publish `data` | ESP32 | `esp32-01` |
| [`wemos-gateway/`](wemos-gateway/) | TODO: peran gateway / relay | Wemos D1 mini | `wemos-01` |

> TODO: konfirmasi perannya. Jika tertukar, tukar nama folder dan perbarui tabel ini, `docs/hardware.id.md`, serta README root.

## Konvensi umum

| Item | Aturan |
|---|---|
| Build system | PlatformIO (`platformio.ini` per folder) |
| Entry point | `src/main.cpp` |
| Rahasia | Kredensial WiFi TIDAK di-commit — pakai `include/config.h` (diabaikan git) atau build flags |
| Identitas device | `DEVICE_ID` harus unik dan sama dengan segmen topik MQTT |
| Payload | Ikuti persis [../docs/mqtt-topics.id.md](../docs/mqtt-topics.id.md) |
| Versi | String `FW_VERSION`, dikirim di `status` |

## Build dan flash

```bash
cd esp32-sensor-node
pio run                  # kompilasi saja
pio run -t upload        # flash
pio device monitor -b 115200
```

Jika memakai Arduino IDE, pertahankan nama folder sama dengan nama sketch `.ino` agar build tetap jalan. PlatformIO lebih disarankan karena pin dan versi library ikut tersimpan di version control.

## Menambah board baru

1. Buat `firmware/<peran>/` berisi `src/main.cpp`, `platformio.ini`, `README.md`.
2. Tambahkan ke tabel di atas dan ke `docs/hardware.id.md`.
3. Daftarkan di DB: `INSERT INTO devices (device_id, board_type, role) VALUES (...);`
4. Publish ke `smartgreengarden/<device-id>/data` dan set Last Will pada `status`.