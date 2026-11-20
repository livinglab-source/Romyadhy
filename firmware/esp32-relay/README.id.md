# Kontroler Relay ESP32

[English](README.md) | [Bahasa Indonesia](README.id.md)

Mengontrol relay AC dan DC untuk pompa irigasi, dinamo pengaduk nutrisi, pompa kuras, dan motorized valve berdasarkan perintah MQTT.

- Peran: node aktuator / relay
- Board: ESP32 DevKit (WROOM-32)
- Client ID MQTT: `ESP32_Hidroponik_Client`

## Tanggung Jawab

- Mengontrol 5 aktuator: pompa irigasi, motor pengaduk, pompa kuras DC, valve pembuangan, valve tandon
- Menjalankan sekuens interlock berpewaktu untuk pengurasan (`kuras_tandon` dan `kuras`)
- Kontrol langsung ON/OFF untuk irigasi dan pengaduk
- Failsafe saat boot: semua pin relay dipaksa MATI (`HIGH`) seketika saat menyala
- Hardware watchdog timer (`esp_task_wdt`) dengan batas waktu 10 detik
- Auto-reconnect WiFi (restart otomatis jika gagal setelah 15 detik) dan MQTT (retry tiap 5 detik)

## Perangkat Keras & Pinout

Semua output relay menggunakan **logika active-LOW**:
- `digitalWrite(pin, LOW)` = **ON / AKTIF**
- `digitalWrite(pin, HIGH)` = **OFF / MATI** (default saat boot)

| Aktuator | Tipe | GPIO | Logika | Keterangan |
|---|---|---|---|---|
| Pompa Irigasi | AC | GPIO 26 | Active LOW | Pompa sirkulasi/irigasi utama |
| Pengaduk Tandon | AC | GPIO 25 | Active LOW | Dinamo pengaduk larutan nutrisi |
| Pompa Kuras | DC | GPIO 27 | Active LOW | Pompa DC pengurasan |
| Valve Kuras | DC | GPIO 13 | Active LOW | Valve pembuangan keluar (drain out) |
| Valve Tandon | DC | GPIO 32 | Active LOW | Valve pemilih tandon |

Tabel wiring: [../../docs/hardware.id.md](../../docs/hardware.id.md#wiring--kontroler-relay-esp32)

## Langganan MQTT (Subscription)

Kontroler mendengarkan topik perintah berikut:

| Topik | Payload | Aktuator / Sekuens yang Dikontrol |
|---|---|---|
| `smartgarden/relay/pompa_irigasi/command` | `1` / `0` | Kontrol langsung ON/OFF: Pompa Irigasi (GPIO 26) |
| `smartgarden/relay/pengaduk_tandon/command` | `1` / `0` | Kontrol langsung ON/OFF: Pengaduk Tandon (GPIO 25) |
| `smartgarden/relay/valve_tandon/command` | `1` / `0` | Kontrol langsung ON/OFF: Valve Tandon (GPIO 32) |
| `smartgarden/relay/pompa_kuras/command` | `1` / `0` | Kontrol langsung ON/OFF: Pompa Kuras DC (GPIO 27) |
| `smartgarden/relay/pengurasan_tandon/command` | `1` / `0` | Sekuens Berpewaktu: Pengurasan tandon (lihat di bawah) |
| `smartgarden/relay/pengurasan/command` | `1` / `0` | Sekuens Berpewaktu: Pembuangan keluar (lihat di bawah) |

> **Catatan Prefix Topik:** Sketch saat ini mendengarkan pada prefix `smartgarden/relay/...`. Prefix default bot Telegram adalah `smartgreengarden`. Jika dikontrol lewat bot, pastikan `MQTT_TOPIC_PREFIX` di file `.env` sesuai dengan firmware, atau sesuaikan konstanta di sketch. Lihat [../../docs/mqtt-topics.id.md](../../docs/mqtt-topics.id.md#topik-lama).

## Sekuens Pengurasan (Interlock Berpewaktu)

Untuk mencegah kavitasi pompa atau lonjakan tekanan terhadap valve yang tertutup, kontroler menerapkan urutan waktu:

### 1. Pengurasan Tandon (`smartgarden/relay/pengurasan_tandon/command`)
- **MULAI (`1`):**
  1. Menutup Valve Kuras (`GPIO 13` -> OFF)
  2. Membuka Valve Tandon (`GPIO 32` -> ON)
  3. Menunggu **500 ms** (`delayTurnOn`) agar valve terbuka fisik
  4. Menyalakan Pompa Kuras DC (`GPIO 27` -> ON)
- **BERHENTI (`0`):**
  1. Menutup Valve Tandon (`GPIO 32` -> OFF)
  2. Menunggu **1500 ms** (`delayTurnOff`) untuk menguras sisa air
  3. Mematikan Pompa Kuras DC (`GPIO 27` -> OFF)

### 2. Pengurasan / Pembuangan Keluar (`smartgarden/relay/pengurasan/command`)
- **MULAI (`1`):**
  1. Menutup Valve Tandon (`GPIO 32` -> OFF)
  2. Membuka Valve Kuras (`GPIO 13` -> ON)
  3. Menunggu **500 ms** (`delayTurnOn`)
  4. Menyalakan Pompa Kuras DC (`GPIO 27` -> ON)
- **BERHENTI (`0`):**
  1. Menutup Valve Kuras (`GPIO 13` -> OFF)
  2. Menunggu **1500 ms** (`delayTurnOff`)
  3. Mematikan Pompa Kuras DC (`GPIO 27` -> OFF)

## Konfigurasi

Kredensial diatur di bagian atas `ESP32-RELAY.ino`:

| Konstanta | Nilai Default | Keterangan |
|---|---|---|
| `ssid` | `"LivingLab"` | WiFi 2.4 GHz |
| `password` | `"LABTengah2026!"` | Password WiFi lab |
| `mqtt_server` | `"192.168.88.88"` | IP broker Raspberry Pi |
| `mqtt_port` | `1883` | Port broker Mosquitto |

## Keamanan & Watchdog

- **Watchdog:** Menggunakan ESP32 Hardware Task Watchdog (`esp_task_wdt`) dengan batas waktu 10 detik. Loop me-reset watchdog pada setiap iterasi. Jika firmware freeze, ESP32 me-restart otomatis.
- **Proteksi WiFi:** Jika WiFi gagal terhubung dalam 15 detik saat boot, ESP32 otomatis me-restart (`ESP.restart()`).
- **State Relay Saat Boot:** Semua 5 pin output diinisialisasi `OUTPUT` dan langsung diset `HIGH` sebelum koneksi jaringan untuk mencegah relay menyala tak disengaja.

## Build dan Flash

```bash
# Arduino IDE:
# 1. Buka firmware/esp32-relay/ESP32-RELAY.ino
# 2. Pilih Board: "ESP32 Dev Module"
# 3. Pilih Port dan Upload
```

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Relay aktif seketika saat board menyala | Inversi active-LOW | Pin harus diset `HIGH` saat inisialisasi di `setup()` |
| Relay tidak bereaksi pada MQTT | Prefix topik tidak cocok | Cek apakah bot mengirim `smartgreengarden/` vs `smartgarden/` |
| Pompa menyala tanpa membuka valve | Melewati sekuens | Kirim perintah ke `pengurasan_tandon` atau `pengurasan`, bukan pin langsung |
| ESP32 terus-menerus reboot | Pemicu watchdog / gagal WiFi | Pantau Serial Monitor di 115200 baud; periksa WiFi |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)
