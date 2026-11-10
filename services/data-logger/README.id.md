# Data Logger

[English](README.md) | [Bahasa Indonesia](README.id.md)

Entry point: [`dataSave.py`](dataSave.py)

Subscribe topik sensor dan menyimpan setiap reading ke MariaDB, dengan salinan opsional ke Firebase Realtime Database.

## Tanggung jawab

- Subscribe `<prefix>/sensor/data`
- Membuat tabel `hydroponic_water_data_romy` bila belum ada
- Meratakan payload JSON menjadi satu baris, menurunkan kategori level tandon
- Insert ke MariaDB **dan**, jika dikonfigurasi, menulis record yang sama ke Firebase RTDB
- Mencatat peringatan bila tidak ada pesan masuk lebih lama dari perkiraan (watchdog)

Ini **satu-satunya** layanan yang menulis reading sensor. Tidak ada bridge terpisah — logger subscribe langsung.

## 1. Konfigurasi

Semua nilai dari environment; file tidak memuat rahasia.

```bash
cp ../../.env.example ../../.env     # sekali, di root repo
```

| Key | Wajib | Default | Arti |
|---|---|---|---|
| `MQTT_HOST` / `MQTT_PORT` | tidak | `localhost` / `1883` | Alamat broker |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | tidak | — | Kredensial broker |
| `MQTT_TOPIC_PREFIX` | tidak | `smartgreengarden` | Akar topik |
| `DB_HOST` / `DB_PORT` | tidak | `localhost` / `3306` | Alamat MariaDB |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | **ya** | — | Kredensial MariaDB |
| `DB_TABLE` | tidak | `hydroponic_water_data_romy` | Tabel tujuan |
| `SAVE_THROTTLE_SECONDS` | tidak | `60` | Jarak minimum antar baris tersimpan |
| `EXPECTED_INTERVAL_SECONDS` | tidak | `300` | Ambang watchdog |
| `LOG_DIR` | tidak | `./logs` | Lokasi log |
| `LOG_BACKUP_COUNT` | tidak | `30` | Jumlah file log rotasi yang disimpan |
| `FIREBASE_CRED_PATH` | tidak | — | JSON service account; kosong = cloud upload mati |
| `FIREBASE_DATABASE_URL` | tidak | — | URL RTDB |
| `FIREBASE_RTDB_ROOT` | tidak | `Hydroponic_Data` | Path root di RTDB |

> Firebase opsional. Dengan `FIREBASE_CRED_PATH` kosong logger tetap jalan — hanya melewati penulisan cloud dan mencatat satu peringatan.

## 2. Menjalankan

```bash
cd services/data-logger
pip install -r requirements.txt
python dataSave.py
```

Atau dari root repo: `scripts/run_services.sh`. Di systemd: `deploy/systemd/data-logger.service`.

Nilai `DB_*` yang hilang langsung menghentikan proses dengan `RuntimeError: Missing required environment variable`.

## 3. Payload → kolom

Input pada `<prefix>/sensor/data`:

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

| Key payload | Kolom | Catatan |
|---|---|---|
| — | `datetime` | Waktu server saat insert (`datetime.now()`) |
| `tds1` | `tds1_ppm` | DECIMAL(10,2) |
| `tds2` | `tds2_ppm` | DECIMAL(10,2) |
| `delta_tds` | `delta_tds` | DECIMAL(5,2) |
| `turbidity` | `turbidity` | DECIMAL(10,2) |
| `flowrate` (atau `flowRate`) | `flow_rate` | Kedua ejaan diterima |
| `level1`–`level4` | `water_level_N_percent` | DECIMAL(5,2) |
| `level1`–`level4` | `water_level_N_status` | Turunan: Empty / Low / Medium / High / Full |
| `water_quality` | `water_quality` | Disimpan sebagai **kode integer** (0–4, `-1` tidak diketahui) |
| hasil cloud | `uploaded_to_cloud` | `1` bila penulisan Firebase berhasil |

Key yang hilang menjadi `0.0`, bukan menggagalkan baris, sehingga payload parsial tetap masuk tabel.

### Kategori level

| Persen | Kategori |
|---|---|
| ≤ 0 | Empty |
| ≤ 25 | Low |
| ≤ 50 | Medium |
| ≤ 75 | High |
| > 75 | Full |

Perhatikan ini berbeda dari ambang tampilan bot (30 / 75 / 100). Keduanya independen; jangan diasumsikan sama.

## 4. Throttling

`on_message` mencatat `last_message_time` untuk **setiap** pesan (agar watchdog melihat trafik), tetapi hanya menulis baris jika `SAVE_THROTTLE_SECONDS` sudah lewat sejak simpan terakhir.

| Situasi | Hasil |
|---|---|
| ESP32 publish tiap 5 detik | Satu baris per menit |
| Broker mati | Tidak ada baris; watchdog memperingatkan setelah `EXPECTED_INTERVAL_SECONDS` |
| Pesan retained saat start | Langsung disimpan (pesan pertama selalu lolos) |

Pesan yang dilewati dicatat di `INFO`: `⏭️ Message received but skipped (within 60s throttle window)`.

## 5. Salinan Firebase

Bila diaktifkan, setiap record juga ditulis ke:

```
<FIREBASE_RTDB_ROOT>/<YYYY-MM-DD>/<HH-MM>
```

Satu node per menit, ditimpa bila dua record jatuh di menit yang sama. Isinya sama dengan baris MySQL ditambah `timestamp_iso`.

Kegagalan cloud **tidak** memblokir insert MySQL — dicatat di log dan `uploaded_to_cloud` diset `0`. Kolom itu penanda rekonsiliasi: `SELECT * FROM hydroponic_water_data_romy WHERE uploaded_to_cloud = 0;`

JSON kredensial adalah private key. Diabaikan git (`*firebase*adminsdk*.json`) dan tidak boleh di-commit.

## 6. Logging

| Properti | Nilai |
|---|---|
| File | `LOG_DIR/garden.log` |
| Rotasi | Harian tengah malam |
| Kompresi | gzip (`.gz`) |
| Retensi | `LOG_BACKUP_COUNT` file |
| Console | dicerminkan pada level yang sama |

Pesan watchdog berbentuk:

```
⏰ No MQTT message received for 412s (expected every ~300s).
```

Baris itu adalah bukti bahwa celah data berasal dari masalah sensor/jaringan, bukan kegagalan logger yang senyap.

## 7. Verifikasi

```bash
mysql -u livinglab -p livinglab -e "SELECT * FROM hydroponic_water_data_romy ORDER BY id DESC LIMIT 5;"
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM hydroponic_water_data_romy;"
tail -f services/data-logger/logs/garden.log
```

Urutan log sehat:

```
✅ Successfully connected to Local MQTT Broker
📥 Listening to topic: smartgreengarden/sensor/data
📩 [2026-11-10 14:30:02] Message received and PROCESSING...
🗄️ Data successfully saved to MySQL.
```

## 8. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `RuntimeError: Missing required environment variable` | `.env` tidak dimuat | `EnvironmentFile=` pada unit, atau jalankan dari root repo |
| `Error setting up database` lalu keluar | DB mati atau kredensial salah | Cek `DB_*`, `systemctl status mariadb` |
| Terhubung tapi tidak ada baris | Prefix topik salah | Bandingkan `MQTT_TOPIC_PREFIX` dengan firmware, cek via `mosquitto_sub` |
| Baris muncul maksimal sekali per menit | Throttle bekerja sesuai desain | Turunkan `SAVE_THROTTLE_SECONDS` saat uji |
| `Error processing JSON data` | Payload cacat | Perbaiki pengirim; payload mentah tercatat di log |
| `flow_rate` selalu 0 | Payload memakai key lain | Kirim `flowrate` atau `flowRate` |
| `water_quality` bernilai -1 | Nilai hilang atau bukan angka | Cek keluaran klasifikasi ESP32 |
| `uploaded_to_cloud` selalu 0 | Firebase belum dikonfigurasi atau gagal | Cek `FIREBASE_*`, baca alasan di log |
| Tidak ada peringatan watchdog tapi data kosong | Logger tidak berjalan | `systemctl status data-logger` |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)