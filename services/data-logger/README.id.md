# Data Logger

[English](README.md) | [Bahasa Indonesia](README.id.md)

Menyimpan reading sensor ke MariaDB.

- Bahasa: Python 3.11
- Unit: `deploy/systemd/data-logger.service`
- Bergantung pada: Mosquitto, MariaDB

## Tanggung jawab

- Menerima reading tervalidasi dari bridge
- Insert ke `readings` dengan tipe kolom yang benar
- Upsert `device_status` setiap pesan `status`
- Tetap hidup jika DB sempat tidak tersedia (retry, jangan crash)

**Tidak** memvalidasi bentuk payload (itu tugas bridge) dan **tidak** mengirim notifikasi.

## Konfigurasi

| Key | Arti |
|---|---|
| `DB_HOST` / `DB_PORT` | Alamat MariaDB |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Kredensial |
| `MQTT_HOST` / `MQTT_PORT` | Alamat broker |
| `LOG_LEVEL` | `INFO` normal |

## Jalankan

```bash
cd services/data-logger
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Verifikasi

```bash
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM readings;"
mysql -u livinglab -p livinglab -e "SELECT * FROM readings ORDER BY id DESC LIMIT 5;"
```

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Count tetap 0 | Tidak menerima / insert gagal | Cek log untuk error SQL |
| Error FK saat insert | Device belum ada di `devices` | `INSERT INTO devices (device_id, board_type, role) VALUES (...)` |
| `Incorrect decimal value` | Nilai di luar jangkauan `DECIMAL(5,2)` | Perbaiki payload atau lebarkan kolom lewat migrasi |
| Insert lambat | Index hilang / tabel besar | Pastikan `idx_readings_device_time`; terapkan retensi |

Referensi skema: [../../db/schema.sql](../../db/schema.sql) · [../../docs/database.id.md](../../docs/database.id.md)