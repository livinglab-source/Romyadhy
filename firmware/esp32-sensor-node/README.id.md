# Node Sensor ESP32

[English](README.md) | [Bahasa Indonesia](README.id.md)

Membaca sensor lingkungan dan publish ke MQTT setiap `PUBLISH_INTERVAL_MS`.

- Peran: node sensor
- Board: ESP32 — TODO: varian persis (mis. DevKit V1 / WROOM-32)
- Device id: `esp32-01` — TODO: buat unik jika ada lebih dari satu

## Tanggung jawab

- Membaca TODO: daftar sensor (mis. DHT22, BME280)
- Publish `smartgreengarden/esp32-01/data` setiap N detik
- Publish `smartgreengarden/esp32-01/status` (retained) + daftarkan Last Will
- Subscribe `smartgreengarden/esp32-01/cmd` dan menjalankannya

## Perangkat keras

| Komponen | Model | Catatan |
|---|---|---|
| MCU | ESP32 TODO | Hanya WiFi 2.4 GHz |
| Sensor | TODO | TODO: tegangan, protokol (one-wire / I2C) |
| Daya | TODO | Pakai catu daya yang kuat terhadap lonjakan arus WiFi |

Tabel wiring: [../../docs/hardware.id.md](../../docs/hardware.id.md#wiring--node-sensor-esp32)

## Konfigurasi

Rahasia tidak di-commit. Buat `include/config.h` dari contoh:

```bash
cp include/config.h.example include/config.h
```

| Key | Lokasi | Arti |
|---|---|---|
| `WIFI_SSID` / `WIFI_PASSWORD` | `include/config.h` | WiFi lab (2.4 GHz) |
| `MQTT_HOST` | `include/config.h` | IP LAN Raspberry Pi |
| `MQTT_PORT` | `include/config.h` | `1883` |
| `MQTT_USER` / `MQTT_PASS` | `include/config.h` | Kredensial Mosquitto |
| `DEVICE_ID` | `include/config.h` | Harus sama dengan segmen topik |
| `PUBLISH_INTERVAL_MS` | `include/config.h` | Default 30000 |
| `FW_VERSION` | build flag `platformio.ini` | Dikirim di `status` |

## MQTT

Kontrak: [../../docs/mqtt-topics.id.md](../../docs/mqtt-topics.id.md)

| Arah | Topik | Payload |
|---|---|---|
| publish | `smartgreengarden/esp32-01/data` | `{"schema":1,"device_id":"esp32-01","ts":...,"temp":27.45,"hum":61.2}` |
| publish (retained) | `smartgreengarden/esp32-01/status` | `{"schema":1,"online":true,"rssi":-67,"uptime_s":...,"fw":"1.0.0"}` |
| subscribe | `smartgreengarden/esp32-01/cmd` | `{"schema":1,"action":"set_interval","value":10000}` |

Last Will pada `status`: `{"schema":1,"device_id":"esp32-01","online":false}`

## Build dan flash

```bash
pio run                  # kompilasi
pio run -t upload        # flash lewat USB
pio device monitor -b 115200
```

## Troubleshooting

| Gejala | Kemungkinan penyebab | Solusi |
|---|---|---|
| Boot loop / brownout | Catu daya terlalu lemah | PSU lebih baik, kapasitor dekat 3V3 |
| WiFi tidak pernah konek | Jaringan 5 GHz atau salah ketik | Pakai 2.4 GHz; cek `WIFI_SSID` |
| MQTT terus reconnect | `DEVICE_ID` duplikat | Buat unik per board |
| Publish jalan tapi DB kosong | Key payload tidak cocok / device belum terdaftar | Cek `docs/mqtt-topics.id.md`, insert ke `devices` |
| Nilai salah | Pin salah atau pull-up kurang | Cocokkan dengan `#define` dan tabel wiring |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)