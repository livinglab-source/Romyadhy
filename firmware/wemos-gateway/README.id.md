# Gateway Wemos — Node Level Air

[English](README.md) | [Bahasa Indonesia](README.id.md)

Dua board Wemos D1 Mini (A dan B), masing-masing membaca 2 sensor level air via ADS1115 dan mempublikasikan ke MQTT setiap 30 detik.

| Node | Sketch | Client ID MQTT | Topik | Sensor |
|---|---|---|---|---|
| Wemos A | `wemos_a_waterlevel_code.ino` | `WEMOS_A` | `smartgreengarden/waterlevel/wemosA` | Level 1 & 2 |
| Wemos B | `wemos_b_waterlevel_code.ino` | `WEMOS_B` | `smartgreengarden/waterlevel/wemosB` | Level 3 & 4 |

## Tanggung jawab

- Menyalakan tiap sensor secara terpisah (D5 / D6) untuk mengurangi korosi
- Merata-rata 50 pembacaan ADS1115 per siklus pengukuran
- Menerapkan kalibrasi linear per sensor (adc_min → 0%, adc_max → 100%)
- Menerapkan deadband (10% dari range mulai adc_min) untuk meredam noise saat hampir kosong
- Publish nilai level % dan cm ke MQTT (retained); mendaftarkan LWT `{"offline":true}`
- Auto-reconnect WiFi (setiap 10 detik) dan MQTT (setiap 5 detik) tanpa blocking

## Perangkat keras

Kedua node memiliki hardware identik — hanya nilai kalibrasi dan client/topik MQTT yang berbeda.

| Komponen | Model | Catatan |
|---|---|---|
| MCU | Wemos D1 mini (ESP8266) | Hanya WiFi 2.4 GHz |
| ADC ekspander | ADS1115 | Alamat I²C 0x48, GAIN_ONE (±4.096 V) |
| Sensor level A/B | Resistif analog (×2 per node) | Power-gated via GPIO |

Wiring: [../../docs/hardware.id.md](../../docs/hardware.id.md#wiring--wemos-a--b-node-level-air)

## Konfigurasi

Kredensial di-hardcode di tiap sketch. Ubah sebelum flash:

| Konstanta | Wemos A | Wemos B |
|---|---|---|
| `ssid` | `LivingLab` | `LivingLab` |
| `password` | (lihat sketch) | (lihat sketch) |
| `mqtt_server` | `192.168.88.88` | `192.168.88.88` |
| `mqtt_client_id` | `WEMOS_A` | `WEMOS_B` |
| `mqtt_topic` | `smartgreengarden/waterlevel/wemosA` | `smartgreengarden/waterlevel/wemosB` |
| `PUBLISH_INTERVAL_MS` | 30000 | 30000 |

## MQTT

Kontrak: [../../docs/mqtt-topics.id.md](../../docs/mqtt-topics.id.md)

### Wemos A — `smartgreengarden/waterlevel/wemosA`

```json
{"level1": 88, "level1_cm": 3.52, "level2": 64, "level2_cm": 2.56}
```

### Wemos B — `smartgreengarden/waterlevel/wemosB`

```json
{"level3": 41, "level3_cm": 1.64, "level4": 27, "level4_cm": 1.08}
```

Kedua topik dipublish sebagai **retained**. LWT `{"offline":true}` didaftarkan setiap koneksi.

## Kalibrasi

Setiap sensor memerlukan satu kali kalibrasi kering + basah. Firmware sudah memiliki mode terpandu bawaan.

### Langkah-langkah

**Langkah 1 — Kalibrasi kering (adc_min)**
1. Pastikan kedua sensor benar-benar kering
2. Set `CAL_MODE_DRY true`, `CAL_MODE_WET false` di sketch
3. Flash → buka Serial Monitor di 115200 baud
4. Salin saran `adc_min` yang tercetak ke `calS1`/`calS2` (atau `calS3`/`calS4`)
5. Set `CAL_MODE_DRY false`

**Langkah 2 — Kalibrasi basah (adc_max)**
1. Celupkan kedua sensor sampai kedalaman maksimum dalam larutan nutrisi asli
2. Set `CAL_MODE_WET true`, `CAL_MODE_DRY false`
3. Flash → buka Serial Monitor
4. Salin saran `adc_max` yang tercetak ke struct
5. Set `CAL_MODE_WET false`

**Langkah 3 — Operasi normal**
Kedua flag `false` → flash → perangkat berjalan normal.

### Nilai kalibrasi saat ini

| Node | Sensor | `adc_min` | `adc_max` | `sensor_len_mm` |
|---|---|---|---|---|
| Wemos A | S1 (Ch0) | 4941 | 7246 | 40.0 |
| Wemos A | S2 (Ch1) | 4015 | 32767 | 40.0 |
| Wemos B | S3 (Ch0) | 2250 | 6450 | 40.0 |
| Wemos B | S4 (Ch1) | 1007 | 5500 | 40.0 |

> `adc_max = 32767` pada S2 artinya kalibrasi basah untuk sensor tersebut belum dilakukan.

### Diagnosis noise (dicetak saat kalibrasi)

| Spread | Kesimpulan |
|---|---|
| < 50 | STABIL — hasil dapat dipercaya |
| 50–150 | SEDANG — noise kecil, masih oke |
| > 150 | NOISE TINGGI — cek GND dan jalur sensor |

## Build dan flash

```bash
# Arduino IDE — buka .ino, pilih "LOLIN(Wemos) D1 R2 & mini", flash
# atau PlatformIO:
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Gejala | Kemungkinan penyebab | Solusi |
|---|---|---|
| LED berkedip cepat saat boot | ADS1115 tidak ditemukan | Cek wiring I²C (SDA=D2, SCL=D1, ADDR=GND→0x48) |
| WiFi tidak pernah konek | SSID salah / jaringan 5 GHz | Update `ssid`/`password`; gunakan 2.4 GHz |
| MQTT terus reconnect | IP salah atau broker mati | Verifikasi `mqtt_server`; `ping 192.168.88.88` |
| Level selalu 0 | Deadband terpicu / kalibrasi kering meleset | Ulangi kalibrasi kering; cek wiring channel ADS1115 |
| Level selalu 100 | adc_max terlalu rendah / kalibrasi basah belum dilakukan | Ulangi kalibrasi basah |
| Pembacaan tidak stabil | Spread noise tinggi saat kalibrasi | Cek GND sensor dan wiring pin power-gate |
| Error client id duplikat | Dua node dengan `mqtt_client_id` yang sama | Pastikan A pakai `WEMOS_A` dan B pakai `WEMOS_B` |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)
