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

### Payload `sensor/data`

```json
{
  "tds1": 812.4,
  "tds2": 795.1,
  "delta_tds": 17.3,
  "turbidity": 12.5,
  "flowrate": 6.2,
  "level1": 88,
  "level2": 64,
  "level3": 41,
  "level4": 27,
  "water_quality": "2"
}
```

| Key | Satuan | Rentang | Arti |
|---|---|---|---|
| `tds1` | ppm | 0–2000 | Probe TDS 1 (larutan nutrisi) |
| `tds2` | ppm | 0–2000 | Probe TDS 2 |
| `delta_tds` | % | 0–100 | Selisih kedua probe |
| `turbidity` | NTU | 0–100 | ≤50 jernih, >50 keruh |
| `flowrate` | L/min | 0–30 | Debit irigasi |
| `level1` | % | 0–100 | Tandon 1 — utama |
| `level2` | % | 0–100 | Tandon 2 — bak pencampur |
| `level3` | % | 0–100 | Tandon 3 — buffer nutrisi |
| `level4` | % | 0–100 | Tandon 4 — pembuangan/overflow |
| `water_quality` | kode | 0–4 | Lihat di bawah |

Kode `water_quality`:

| Kode | Arti |
|---|---|
| `0` | 🟡 Keruh — suspensi nutrisi |
| `1` | 🟤 Keruh — sedimen |
| `2` | 🟢 Normal / jernih |
| `3` | 🟠 Ketidakseimbangan nutrisi |
| `4` | 🔴 Level air rendah |

Bot menghitung ulang kode ini dari nilai mentah sebelum ditampilkan, jadi kode usang pada payload tidak bisa menyesatkan dashboard. Kirim `"nan"` hanya jika probe gagal — bot menggantinya dengan `0.0` dan nilai itu dikeluarkan dari statistik.

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

| Topik | Arah | Payload |
|---|---|---|
| `smartgreengarden/sensor/calibrate/tds1/multi/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/tds1/multi/set` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/kalibrasi/tds1` | bot → ESP32 | `<ppm>` (single-point) |
| `smartgreengarden/sensor/calibrate/tds2/multi/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/tds2/multi/set` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/kalibrasi/tds2` | bot → ESP32 | `<ppm>` |
| `smartgreengarden/sensor/calibrate/turbidity/start` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/next` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/cancel` | bot → ESP32 | `1` |
| `smartgreengarden/sensor/calibrate/turbidity/status` | ESP32 → bot | teks bebas |

Rentang valid: TDS 0–5000 ppm. Urutan turbidity 0 → 50 → 100 NTU, dilanjutkan dengan `/next`.

Perhatikan ejaan yang tidak konsisten — `kalibrasi` untuk TDS single-point, `calibrate` di tempat lain. Ini warisan dari firmware dan sengaja tidak diubah di sini agar setup yang sudah jalan tidak rusak. Jika ingin dirapikan, ubah kedua sisi dalam satu commit.

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