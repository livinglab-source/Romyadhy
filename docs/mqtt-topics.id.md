# Topik MQTT (Kontrak)

[English](mqtt-topics.md) | [Bahasa Indonesia](mqtt-topics.id.md)

> **Dokumen ini adalah kontrak.** Firmware dan layanan Python harus sepakat.
> Mengganti nama topik atau key payload adalah **breaking change** — perbarui kedua sisi dan catat di sini.

## Prefix root

Semua topik diawali `MQTT_TOPIC_PREFIX`, default `smartgreengarden`.

```
smartgreengarden/<path>
```

Bot dan firmware membangun topik dari prefix ini, jadi memakai prefix lain adalah perubahan konfigurasi, bukan perubahan kode.

> Catatan sejarah: firmware lama memakai root terpisah `smartgarden/...` untuk relay dan mode. Bot sekarang mem-publish semuanya di bawah satu prefix `smartgreengarden`. Jika firmware Anda masih mendengarkan `smartgarden/relay/...`, samakan — lihat [Topik lama](#topik-lama).

## Data sensor

| Topik | Arah | Payload |
|---|---|---|
| `smartgreengarden/sensor/data` | ESP32 → bot | JSON, lihat di bawah |
| `smartgreengarden/sensor/request_data` | bot → ESP32 | `1` — minta reading segera |
| `smartgreengarden/notification` | ESP32 → bot | `{"alert": "...", "level": "warning"}` |
| `smartgreengarden/waterlevel/wemosA` | Wemos A → bot | JSON, lihat di bawah (retained) |
| `smartgreengarden/waterlevel/wemosB` | Wemos B → bot | JSON, lihat di bawah (retained) |

### Payload `sensor/data`

> **Kapitalisasi key penting.** Firmware menggunakan kapitalisasi campuran — konsumen harus mencocokkan persis.

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

| Key | Satuan | Rentang | Arti |
|---|---|---|---|
| `tds1` | ppm | 0–2000 | Probe TDS 1 (ADS1115 AIN2) |
| `tds2` | ppm | 0–2000 | Probe TDS 2 (ADS1115 AIN3) |
| `turbidity` | NTU | 0–∞ | Dihitung sebagai `A × tegangan + B`; minimum dipatok ke 0 |
| `voltage_turbidity` | V | 0–4.096 | Tegangan mentah ADS1115 AIN0, 3 desimal |
| `FlowRate` | L/min | 0–∞ | Dihitung sebagai `jumlah_pulsa / 7.5` per detik |
| `Level1`–`Level4` | % | 0–100 | Level air, dilinearisasi dari ADC dengan kalibrasi per sensor |
| `adc_level1`–`adc_level4` | raw | 0–4095 | Nilai ADC mentah ESP32 sebelum linearisasi |

Firmware **tidak** mengirim `delta_tds` maupun `water_quality` — keduanya dihitung oleh bot dari nilai mentah di atas. Kirim `"nan"` hanya jika probe gagal; bot menggantinya dengan `0.0` dan mengecualikannya dari statistik.

### Payload `waterlevel/wemosA`

```json
{"level1": 88, "level1_cm": 3.52, "level2": 64, "level2_cm": 2.56}
```

### Payload `waterlevel/wemosB`

```json
{"level3": 41, "level3_cm": 1.64, "level4": 27, "level4_cm": 1.08}
```

| Key | Satuan | Rentang | Arti |
|---|---|---|---|
| `level1`–`level4` | % | 0–100 | Persentase level air (dilinearisasi dari ADC ADS1115) |
| `level1_cm`–`level4_cm` | cm | 0–4.0 | Kedalaman dalam cm (strip sensor = 40 mm) |

Kedua topik bersifat **retained**. LWT `{"offline":true}` didaftarkan setiap koneksi — broker mempublikasikannya jika node mati.

### Payload `notification`

```json
{ "alert": "Turbidity above 80 NTU", "level": "warning" }
```

`level` opsional; salah satu dari `critical`, `warning`, `info`, `system`. Jika tidak ada, bot menyimpulkan: pesan yang memuat *normal*, *ok*, *success*, *info*, atau *cleared* menjadi `info`, sisanya `warning`.

## Relay dan mode

| Topik | Arah | Payload |
|---|---|---|
| `smartgreengarden/system/mode` | dua arah | `auto` / `manual` |
| `smartgreengarden/relay/pompa_irigasi/command` | dua arah | `1` / `0` |
| `smartgreengarden/relay/pengurasan_tandon/command` | dua arah | `1` / `0` |
| `smartgreengarden/relay/pengurasan/command` | dua arah | `1` / `0` |
| `smartgreengarden/relay/pengaduk_tandon/command` | dua arah | `1` / `0` |
| `smartgreengarden/relay/valve_tandon/command` | dua arah | `1` / `0` |
| `smartgreengarden/relay/pompa_kuras/command` | dua arah | `1` / `0` |

Ini **sengaja dua arah**: bot mem-publish perintah, lalu firmware mem-publish state hasilnya ke topik yang sama. Itulah cara panel relay tetap jujur setelah perubahan yang dipicu otomasi.

| Relay | Perangkat fisik |
|---|---|
| `pompa_irigasi` | Pompa irigasi |
| `pengurasan_tandon` | Sekuens pengurasan tandon |
| `pengurasan` | Sekuens pengurasan |
| `pengaduk_tandon` | Pengaduk tandon |
| `valve_tandon` | Valve tandon (langsung) |
| `pompa_kuras` | Pompa kuras (langsung) |

`system/mode` juga dua arah: `/mode manual` mem-publish-nya, dan firmware menggemakannya agar bot menampilkan state nyata, bukan yang diharapkan.

## Kalibrasi

Firmware berlangganan topik berikut untuk kalibrasi TDS jarak jauh. Kalibrasi turbiditas hanya bisa dilakukan via serial (`CALTURB`).

| Topik | Arah | Payload |
|---|---|---|
| `smartgreengarden/sensor/kalibrasi/tds1` | bot → ESP32 | `<ppm>` (single-point, misal `342`) |
| `smartgreengarden/sensor/kalibrasi/tds2` | bot → ESP32 | `<ppm>` (single-point) |

Rentang valid: TDS 0–5000 ppm. Firmware menyesuaikan K-value dan menyimpannya ke EEPROM.

> Ejaan `kalibrasi` (Indonesia) adalah yang dipakai firmware. Jangan ganti nama tanpa memperbarui firmware sekaligus.

## Topik lama

Revisi firmware lama memakai root `smartgarden/` dan beberapa path berbeda:

| Lama | Sekarang |
|---|---|
| `smartgarden/relay/pompa_irigasi/command` | `smartgreengarden/relay/pompa_irigasi/command` |
| `smartgarden/system/mode` | `smartgreengarden/system/mode` |

Jika relay merespons bot tetapi dashboard tidak (atau sebaliknya), ketidakcocokan ini adalah hal pertama yang perlu dicek: `mosquitto_sub -t 'smartgarden/#' -v` versus `-t 'smartgreengarden/#'`.

## Debugging

```bash
# Semua
mosquitto_sub -t 'smartgreengarden/#' -v

# Kedua root, untuk menangkap firmware lama
mosquitto_sub -t 'smartgarden/#' -t 'smartgreengarden/#' -v

# Hanya data sensor
mosquitto_sub -t 'smartgreengarden/sensor/data' -v

# Hanya alert
mosquitto_sub -t 'smartgreengarden/notification' -v

# Kirim perintah relay manual (melewati bot)
mosquitto_pub -t 'smartgreengarden/relay/pompa_irigasi/command' -m '1'

# Minta reading baru dari ESP32
mosquitto_pub -t 'smartgreengarden/sensor/request_data' -m '1'
```

## Aturan

- Tanpa slash di awal — `/smartgreengarden/...` adalah hierarki berbeda.
- Satu prefix root. Jangan menambah root kedua untuk fitur baru.
- Topik relay dua arah; jangan memutus gemanya.
- Perubahan key payload bersifat breaking: perbarui `services/telegram-bot/telegrambot.py`, firmware, dan file ini dalam satu commit.