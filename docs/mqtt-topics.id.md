# Topik MQTT (Kontrak)

[English](mqtt-topics.md) | [Bahasa Indonesia](mqtt-topics.id.md)

> **Dokumen ini adalah kontrak.** Firmware dan layanan Python harus sepakat.
> Mengubah nama topik atau key payload adalah **breaking change** — naikkan `SCHEMA_VERSION` pada payload dan catat di sini.

## Struktur topik

```
livinglab/<device-id>/<channel>
```

| Bagian | Contoh | Aturan |
|---|---|---|
| Prefix | `livinglab` | Harus sama dengan `MQTT_TOPIC_PREFIX` di `.env` |
| `device-id` | `esp32-01` | Huruf kecil, hanya `[a-z0-9-]`, unik per board fisik |
| `channel` | `data` | Salah satu: `data`, `status`, `cmd`, `alert` |

## Kanal

| Topik | Arah | QoS | Retain | Fungsi |
|---|---|---|---|---|
| `livinglab/<device-id>/data` | device → broker | 1 | tidak | Data sensor |
| `livinglab/<device-id>/status` | device → broker | 1 | **ya** | Online/offline (LWT), RSSI, uptime |
| `livinglab/<device-id>/cmd` | broker → device | 1 | tidak | Perintah (relay on/off, interval) |
| `livinglab/<device-id>/alert` | broker → device | 1 | tidak | Alert ambang batas dari Python |

**Retain pada `status` penting:** bot yang baru dinyalakan bisa membaca status terakhir tanpa menunggu publish berikutnya.

## Payload: `data`

```json
{
  "schema": 1,
  "device_id": "esp32-01",
  "ts": 1731000000,
  "seq": 42,
  "temp": 27.45,
  "hum": 61.2
}
```

| Field | Tipe | Satuan | Wajib | Catatan |
|---|---|---|---|---|
| `schema` | int | — | ya | Naikkan jika ada perubahan breaking |
| `device_id` | string | — | ya | Harus sama dengan segmen topik |
| `ts` | int | Unix detik | ya | Waktu device (`NTP` atau fallback uptime) |
| `seq` | int | — | tidak | Untuk mendeteksi pesan hilang |
| `temp` | float | °C | tergantung | 2 angka desimal |
| `hum` | float | % RH | tergantung | 0–100 |

TODO: tambahkan field lain yang benar-benar dikirim node (misalnya `soil`, `light`, `relay`, `co2`).

## Payload: `status`

```json
{
  "schema": 1,
  "device_id": "esp32-01",
  "online": true,
  "rssi": -67,
  "uptime_s": 86400,
  "fw": "1.0.0"
}
```

Device juga mendaftarkan **Last Will** pada topik ini:

```json
{ "schema": 1, "device_id": "esp32-01", "online": false }
```

sehingga broker otomatis mem-publish-nya jika board terputus.

## Payload: `cmd`

```json
{ "schema": 1, "action": "set_relay", "value": 1, "request_id": "abc123" }
```

| `action` | `value` | Efek |
|---|---|---|
| `set_relay` | `0` / `1` | TODO: jelaskan |
| `set_interval` | detik | Ubah interval publish |
| `reboot` | — | Restart device |

Device sebaiknya mengonfirmasi dengan publish ke `status` berisi `last_request_id`.

## Aturan penamaan topik

- Pakai **id device**, bukan tipe board: `livinglab/esp32-01/data` ✅, `livinglab/esp32/data` ❌
- Hindari satuan di nama field (`temp_c` boleh jika konsisten — yang penting konsisten)
- Jangan pakai slash di awal (`/livinglab/...` membuat hierarki berbeda)
- Wildcard untuk debugging: `mosquitto_sub -t 'livinglab/#' -v`

## Debugging

```bash
# Lihat semua
mosquitto_sub -t 'livinglab/#' -v

# Lihat satu device
mosquitto_sub -t 'livinglab/esp32-01/#' -v

# Hanya status retained
mosquitto_sub -t 'livinglab/+/status' -v -R

# Kirim perintah uji
mosquitto_pub -t 'livinglab/esp32-01/cmd' -m '{"schema":1,"action":"set_relay","value":1}'
```