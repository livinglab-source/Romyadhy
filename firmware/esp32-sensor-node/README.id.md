# Node Sensor ESP32

[English](README.md) | [Bahasa Indonesia](README.id.md)

Membaca sensor kualitas air dan mempublikasikan data ke MQTT setiap `sensorInterval` (5 detik).

- Peran: node sensor
- Board: ESP32 (DevKit / WROOM-32)
- Client ID MQTT: `ESP32_SENSOR`

## Tanggung jawab

- Membaca 2× probe TDS, 1× sensor kekeruhan, 1× flow meter, 4× sensor level air
- Publish `smartgreengarden/sensor/data` setiap 5 detik
- Subscribe `smartgreengarden/sensor/kalibrasi/tds1` dan `tds2` untuk kalibrasi via MQTT
- Menerima perintah serial (`CALTDS1 <ppm>`, `CALTDS2 <ppm>`, `CALTURB`) untuk kalibrasi meja

## Perangkat keras

| Komponen | Model | Catatan |
|---|---|---|
| MCU | ESP32 DevKit (WROOM-32) | Hanya WiFi 2.4 GHz |
| ADC ekspander | ADS1115 | I²C, alamat 0x48, gain GAIN_ONE (±4.096 V) |
| Probe TDS 1 | Gravity TDS | ADS1115 AIN2 |
| Probe TDS 2 | Gravity TDS | ADS1115 AIN3 |
| Sensor kekeruhan | Tegangan analog | ADS1115 AIN0 |
| Sensor aliran | YF-S201 (atau setara) | GPIO 27, interrupt pada RISING |
| Sensor level 1–4 | Resistif analog | GPIO 32, 33, 34, 35 (ADC) |
| VCC sensor level | — | GPIO 26 (daya diputus setelah pembacaan) |
| LCD | 16×2 I²C | Alamat 0x27 |

Tabel wiring: [../../docs/hardware.id.md](../../docs/hardware.id.md#wiring--node-sensor-esp32)

## Konfigurasi

Kredensial di-hardcode langsung di sketch (tidak lewat config.h). Ubah konstanta berikut sebelum flash:

| Konstanta | Lokasi | Arti |
|---|---|---|
| `ssid` / `password` | bagian atas `.ino` | WiFi lab (2.4 GHz) |
| `mqtt_server` | bagian atas `.ino` | IP LAN Raspberry Pi (`192.168.88.88`) |
| `mqtt_port` | bagian atas `.ino` | `1883` |
| `mqtt_client_id` | bagian atas `.ino` | `ESP32_SENSOR` |

Layout EEPROM (512 byte):

| Alamat | Isi |
|---|---|
| 0 | K-value TDS1 (`float`, 4 byte) |
| 10 | K-value TDS2 (`float`, 4 byte) |
| 20 | Slope turbiditas A (`float`, 4 byte) |
| 24 | Intercept turbiditas B (`float`, 4 byte) |

## MQTT

Kontrak: [../../docs/mqtt-topics.id.md](../../docs/mqtt-topics.id.md)

| Arah | Topik | Payload |
|---|---|---|
| publish | `smartgreengarden/sensor/data` | JSON — lihat di bawah |
| subscribe | `smartgreengarden/sensor/kalibrasi/tds1` | `<ppm>` — kalibrasi single-point |
| subscribe | `smartgreengarden/sensor/kalibrasi/tds2` | `<ppm>` — kalibrasi single-point |

### Payload `sensor/data` (key aktual dari firmware)

```json
{
  "tds1": 812.45,
  "tds2": 795.10,
  "turbidity": 12.50,
  "voltage_turbidity": 1.234,
  "FlowRate": 6.20,
  "Level1": 88,
  "adc_level1": 650,
  "Level2": 64,
  "adc_level2": 340,
  "Level3": 41,
  "adc_level3": 480,
  "Level4": 27,
  "adc_level4": 420
}
```

> **Catatan:** Kapitalisasi key tidak konsisten (`FlowRate`, `Level1`–`Level4` kapital; lainnya huruf kecil). Konsumen harus mencocokkan dengan tepat.

## Timer

| Variabel | Interval | Apa yang terjadi |
|---|---|---|
| `sensorInterval` | 5.000 ms | Baca TDS, kekeruhan; publish MQTT |
| `waterLevelInterval` | 60.000 ms | Baca 4 sensor level air |
| `displayInterval` | 3.000 ms | Rotasi LCD ke layar berikutnya (7 layar total) |
| Hitung aliran | 1.000 ms | Hitung L/menit dari jumlah pulsa, lalu reset |

## Kalibrasi

### Via Serial Monitor (115200 baud)

| Perintah | Aksi |
|---|---|
| `CALTDS1 <ppm>` | Kalibrasi single-point TDS1. Menyesuaikan K-value, disimpan ke EEPROM. |
| `CALTDS2 <ppm>` | Kalibrasi single-point TDS2. Menyesuaikan K-value, disimpan ke EEPROM. |
| `CALTURB` | Kalibrasi turbiditas 2-titik interaktif (0 NTU lalu 50 NTU). Simpan A/B ke EEPROM. |

### Via MQTT

Publish `<ppm>` ke `smartgreengarden/sensor/kalibrasi/tds1` atau `tds2`.

### Kalibrasi linear sensor level air

Konstanta kalibrasi di-hardcode di `linear_calibrations[]`. Edit array lalu flash ulang untuk mengubahnya.

| Sensor | ADC min (0%) | ADC max (100%) |
|---|---|---|
| Level 1 | 300 | 687 |
| Level 2 | 200 | 422 |
| Level 3 | 100 | 949 |
| Level 4 | 300 | 717 |

## Build dan flash

```bash
# Arduino IDE — buka keren-12.ino, pilih ESP32 Dev Module, lalu flash
# atau PlatformIO:
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Gejala | Kemungkinan penyebab | Solusi |
|---|---|---|
| Boot loop / `ADS1115 Error!` di LCD | ADS1115 tidak terdeteksi di I²C | Cek wiring dan alamat I²C (0x48) |
| WiFi tidak pernah konek | Jaringan 5 GHz atau kredensial salah | Pakai 2.4 GHz; update `ssid`/`password` di sketch |
| MQTT terus reconnect | IP broker salah atau broker mati | Cek `mqtt_server`; `ping 192.168.88.88` |
| TDS baca 0 atau noise | K-value hilang atau probe lepas | Kirim `CALTDS1 <ppm_diketahui>` atau cek ADS1115 AIN2/3 |
| Turbiditas selalu 0 atau negatif | Kalibrasi belum dilakukan | Kirim `CALTURB` via Serial Monitor |
| Level air tidak bergerak / salah | Mismatch kalibrasi ADC | Update `linear_calibrations[]` dan flash ulang |
| Aliran selalu 0 | Interrupt tidak terpicu | Cek wiring GPIO 27; pastikan `INPUT_PULLUP` |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)
