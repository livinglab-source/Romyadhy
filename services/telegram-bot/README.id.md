# Telegram Bot

[English](README.md) | [Bahasa Indonesia](README.id.md)

Entry point: [`telegrambot.py`](telegrambot.py)

Kontrol dan monitoring Living Lab hidroponik lewat chat: dashboard sensor langsung, kontrol relay, kalibrasi, export CSV, dan alert.

## Tanggung jawab

- Subscribe data sensor MQTT, menyimpan reading terakhir di memori, merender dashboard ASCII
- Mengontrol 6 relay dan mengubah mode sistem `auto` / `manual`
- Menjalankan alur kalibrasi TDS dan turbidity pada ESP32
- Mencatat event relay ON/OFF beserta durasinya ke MariaDB
- Export tabel DB ke CSV lalu mengirimnya sebagai dokumen Telegram
- Mengirim alert (ambang batas, perubahan mode, status kalibrasi)

**Tidak** menulis reading sensor ke database — itu tugas `data-logger`.

## 1. Konfigurasi

Semua dibaca dari environment. Bot tidak pernah memuat rahasia di dalam kode.

```bash
cp ../../.env.example ../../.env     # sekali, di root repo
```

| Key | Wajib | Default | Arti |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ya | — | Dari @BotFather |
| `TELEGRAM_CHAT_ID` | ya | — | Chat penerima update terjadwal dan alert |
| `TELEGRAM_ALLOWED_CHAT_IDS` | tidak | = `TELEGRAM_CHAT_ID` | Id dipisah koma yang boleh memberi perintah |
| `ACCESS_PASSWORD` | ya | — | Password untuk `/login` |
| `SESSION_TIMEOUT_SECONDS` | tidak | `3600` | Sesi kedaluwarsa setelah tidak aktif selama ini |
| `MQTT_HOST` / `MQTT_PORT` | tidak | `127.0.0.1` / `1883` | Alamat broker |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | tidak | — | Kredensial broker |
| `MQTT_TOPIC_PREFIX` | tidak | `smartgreengarden` | Akar semua topik |
| `DB_HOST` / `DB_PORT` | tidak | `127.0.0.1` / `3306` | Alamat MariaDB |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | ya | — | Kredensial MariaDB |
| `DB_TABLE` | tidak | `hydroponic_water_data_romy` | Tabel data sensor |
| `DB_TIME_COLUMN` | tidak | `datetime` | Kolom timestamp |
| `DB_TIME_IS_STRING` | tidak | `false` | `true` jika timestamp disimpan sebagai teks |
| `EXPORT_DIR` | tidak | `./exports` | Lokasi CSV sebelum dikirim |
| `LOG_DIR` | tidak | `./logs` | Lokasi file log |
| `ALLOW_DEV_MODE` | tidak | `false` | Simulasikan data sensor jika MQTT tidak terjangkau |

> Jika MQTT tidak terjangkau dan `ALLOW_DEV_MODE` bukan `true`, bot berhenti alih-alih diam-diam menampilkan data palsu.

## 2. Menjalankan

```bash
cd services/telegram-bot
python3 -m venv ../../.venv && source ../../.venv/bin/activate
pip install -r requirements.txt
python telegrambot.py
```

Atau dari root repo: `scripts/run_services.sh`.

Di systemd: `deploy/systemd/telegram-bot.service`.

Dependensi dipin di [`requirements.txt`](requirements.txt) — perhatikan `mysql-connector-python`, penyedia import `mysql.connector`.

## 3. Autentikasi

Semua perintah kecuali `/login` dan `/logout` memerlukan sesi.

| Perintah | Efek |
|---|---|
| `/login <password>` | Memulai sesi; pesannya langsung dihapus agar password tidak tertinggal di chat |
| `/logout` | Mengakhiri sesi |

Sesi kedaluwarsa setelah `SESSION_TIMEOUT_SECONDS` tanpa aktivitas dan diperbarui pada setiap perintah. Callback inline keyboard juga memeriksa sesi, jadi panel yang kedaluwarsa tidak bisa dipakai.

## 4. Perintah

### Monitoring

| Perintah | Hasil |
|---|---|
| `/all_data` | Dashboard penuh: kualitas air, sensor, 4 bar tandon dengan sparkline |
| `/tanks` | Perbandingan visual 4 tandon |
| `/status` | Mode, status relay, kesegaran data, jumlah baris DB |
| `/tds1`, `/tds2` | Reading TDS, gauge, verdict kesehatan, min/max/avg |
| `/turbidity` | Gauge turbidity dan kondisinya |
| `/delta_tds` | Meter selisih nutrisi |
| `/flowrate` | Kartu statistik flow rate |
| `/level1` … `/level4` | Kartu level per tandon |
| `/water_quality` | Klasifikasi kualitas air |

### Relay dan mode

| Perintah | Contoh |
|---|---|
| `/relaypanel` | Tombol ON/OFF interaktif untuk semua relay |
| `/relay <nama> <on\|off>` | `/relay irigasi on` |
| `/relaylog <nama> [jumlah]` | `/relaylog irigasi 10` |
| `/relaystats [nama] [week]` | `/relaystats irigasi week` |
| `/mode <auto\|manual>` | `/mode manual` |

Nama relay: `irigasi`, `kuras_tandon`, `kuras`, `pengaduk`, `valve_tandon`, `pompa_kuras`.

**Perintah relay ditolak saat sistem dalam mode `auto`.** Ganti dengan `/mode manual` dulu — ini mencegah aksi manual berbenturan dengan otomasi.

### Kalibrasi

| Perintah | Efek |
|---|---|
| `/cal_tds1 start` | Mulai kalibrasi multi-point TDS1 |
| `/cal_tds1 set <ppm>` | Catat titik saat ini (0–5000) |
| `/cal_tds1 single <ppm>` | Kalibrasi single-point |
| `/cal_tds2 ...` | Sama, untuk TDS2 |
| `/calturb` | Mulai kalibrasi turbidity (0 / 50 / 100 NTU) |
| `/next` | Catat titik turbidity berikutnya |
| `/cancelcal` | Batalkan kalibrasi turbidity |

### Database dan export

| Perintah | Efek |
|---|---|
| `/dbstatus` | Ping connection pool |
| `/dbstatus reconnect` | Bangun ulang pool setelah DB mati |
| `/export list` | Tampilkan tabel yang bisa di-export |
| `/export <tabel> [hari]` | Pratinjau jumlah baris, lalu konfirmasi untuk kirim CSV |
| `/help` | Daftar perintah lengkap |

Tabel yang bisa di-export: `sensor_data`, `relay_logs`. CSV dihapus dari disk setelah terkirim.

## 5. Kontrak MQTT

Topik dibangun dari `MQTT_TOPIC_PREFIX` (default `smartgreengarden`).

### Subscribe

| Topik | Payload | Dipakai untuk |
|---|---|---|
| `<prefix>/sensor/data` | JSON: `tds1`, `tds2`, `delta_tds`, `turbidity`, `flowrate`, `level1`–`level4`, `water_quality` | Dashboard langsung |
| `<prefix>/notification` | `{"alert": "...", "level": "warning"}` | Alert ke Telegram |
| `<prefix>/sensor/calibrate/turbidity/status` | teks | Pesan progres kalibrasi |
| `<prefix>/system/mode` | `auto` / `manual` | Menjaga state bot sinkron dengan firmware |
| `<prefix>/relay/<nama>/command` | `1` / `0` | Mencerminkan perubahan relay oleh otomasi |

`level` boleh `critical`, `warning`, `info`, atau `system`; jika tidak ada, bot menyimpulkannya dari teks pesan.

### Publish

| Topik | Payload | Pemicu |
|---|---|---|
| `<prefix>/sensor/request_data` | `1` | `/all_data`, tombol refresh |
| `<prefix>/system/mode` | `auto` / `manual` | `/mode` |
| `<prefix>/relay/pompa_irigasi/command` | `1` / `0` | `/relay irigasi …` |
| `<prefix>/relay/pengurasan_tandon/command` | `1` / `0` | `kuras_tandon` |
| `<prefix>/relay/pengurasan/command` | `1` / `0` | `kuras` |
| `<prefix>/relay/pengaduk_tandon/command` | `1` / `0` | `pengaduk` |
| `<prefix>/relay/valve_tandon/command` | `1` / `0` | `valve_tandon` |
| `<prefix>/relay/pompa_kuras/command` | `1` / `0` | `pompa_kuras` |
| `<prefix>/sensor/calibrate/tds1/multi/start` | `1` | `/cal_tds1 start` |
| `<prefix>/sensor/calibrate/tds1/multi/set` | `<ppm>` | `/cal_tds1 set` |
| `<prefix>/sensor/kalibrasi/tds1` | `<ppm>` | `/cal_tds1 single` |
| `<prefix>/sensor/calibrate/tds2/multi/start` | `1` | `/cal_tds2 start` |
| `<prefix>/sensor/calibrate/tds2/multi/set` | `<ppm>` | `/cal_tds2 set` |
| `<prefix>/sensor/kalibrasi/tds2` | `<ppm>` | `/cal_tds2 single` |
| `<prefix>/sensor/calibrate/turbidity/start` | `1` | `/calturb` |
| `<prefix>/sensor/calibrate/turbidity/next` | `1` | `/next` |
| `<prefix>/sensor/calibrate/turbidity/cancel` | `1` | `/cancelcal` |

Contoh payload sensor:

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

Kode `water_quality`: `0` keruh/nutrisi, `1` keruh/sedimen, `2` normal, `3` ketidakseimbangan nutrisi, `4` level air rendah. Bot menghitung ulang dari nilai mentah agar kode usang pada payload tidak menyesatkan tampilan.

## 6. Tabel database yang dipakai

| Tabel | Fungsi | Kolom yang dipakai |
|---|---|---|
| `hydroponic_water_data_romy` | Riwayat sensor (`DB_TABLE`) | `datetime`, kolom sensor; dihitung dan dibaca untuk export |
| `relay_logs` | Log event relay | `relay_name`, `state`, `event_time`, `duration_seconds`, `mode` |

Bot tidak membuat tabel; keduanya harus sudah ada. Lihat [../../docs/database.id.md](../../docs/database.id.md).

## 7. Perilaku yang perlu diketahui

| Perilaku | Detail |
|---|---|
| Antrean alert | Disimpan di memori (tidak persisten), dikuras setiap 5 detik |
| Status kalibrasi | Dikuras setiap 1 detik |
| Dashboard terjadwal | Pesan sensor lengkap setiap 300 detik ke `TELEGRAM_CHAT_ID` |
| Badge kesegaran | 🟢 <30 s, 🟡 <5 menit, 🔴 lebih lama — bertuliskan "cek ESP32" |
| Sparkline | 10 reading terakhir per sensor, hanya di memori |
| Nilai tidak valid | `nan` pada payload diganti `0.0` sebelum diparse |
| `message is not modified` | Ditahan agar tombol refresh tidak error |

Semua yang hanya ada di memori (riwayat sparkline, antrean alert, timer relay ON) hilang saat restart. `relay_logs` adalah catatan yang permanen.

## 8. Keamanan

- Token, password DB, dan password login **hanya** lewat environment variable. Jangan menempelkannya kembali ke source.
- Jaga `TELEGRAM_ALLOWED_CHAT_IDS` tetap sempit. Siapa pun di daftar itu bisa mengontrol pompa.
- `/login` menghapus pesan password, tetapi riwayat Telegram bukan tempat menyimpan rahasia — ganti `ACCESS_PASSWORD` alih-alih memakainya ulang di tempat lain.
- Log ditulis di `LOG_DIR`; isinya chat id dan teks perintah, jadi diabaikan git.
- Jika token bocor: `/revoke` di @BotFather, buat token baru, update `.env`, `systemctl restart telegram-bot`.

## 9. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `RuntimeError: Missing required environment variable` | `.env` tidak dimuat | Pastikan `EnvironmentFile=` pada unit, atau jalankan dari root repo |
| Bot start lalu keluar | MQTT tidak terjangkau dan `ALLOW_DEV_MODE=false` | Nyalakan broker, perbaiki `MQTT_HOST`, atau set `ALLOW_DEV_MODE=true` untuk demo |
| `ModuleNotFoundError: mysql` | Paket salah terpasang | `pip install -r requirements.txt` (butuh `mysql-connector-python`) |
| Tidak ada balasan | Belum login | `/login <password>` |
| "Access Denied" padahal tadi bisa | Sesi kedaluwarsa | Login lagi |
| Tombol relay tidak bereaksi | Sistem dalam mode `auto` | `/mode manual` |
| `/dbstatus` menampilkan error | DB mati, kredensial salah, atau pool gagal dibuat | Cek `DB_*`, lalu `/dbstatus reconnect` |
| Export bilang 0 baris | Key tabel atau rentang tanggal salah | `/export list`, coba tanpa batas hari |
| Alert tidak pernah masuk | Firmware tidak publish, atau tidak ada baris alert | Cek `mosquitto_sub -t '<prefix>/notification' -v` |
| Dashboard menampilkan "belum ada data" | Belum ada payload sensor diterima | Verifikasi `<prefix>/sensor/data` |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)