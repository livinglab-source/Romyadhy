# Deployment (Raspberry Pi)

[English](deployment.md) | [Bahasa Indonesia](deployment.id.md)

Target: Raspberry Pi OS, Mosquitto, MariaDB, dan layanan Python dijalankan dari venv di Pi.

**Tanpa Docker.** Layanan berjalan langsung dari virtualenv dan dijaga oleh systemd.

## Path yang dipakai

| Item | Path |
|---|---|
| Root proyek | `/home/livinglab/workspace/romy` |
| Virtualenv | `/home/livinglab/workspace/romy/.venv` |
| Konfigurasi | `/home/livinglab/workspace/romy/.env` |
| Kode layanan | `/home/livinglab/workspace/romy/services/` |
| Backup | `/var/backups/livinglab` |

> Di Pi juga tersimpan catatan dan kode proyek lain di bawah `/home/livinglab/workspace/romy`. Repo ini hanya mendokumentasikan pipeline IoT; untuk sisanya rujuk catatan lokal tersebut.

## 1. Prasyarat

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients mariadb-server python3-venv python3-pip git
```

## 2. Ambil kode

```bash
cd /home/livinglab/workspace
git clone <repo-url> romy
cd romy
```

Jika folder sudah ada, ini adalah pembaruan: `git pull` (lihat §11).

## 3. Mosquitto

`/etc/mosquitto/conf.d/livinglab.conf` — salinannya tersimpan di [`deploy/mosquitto/mosquitto.conf`](../deploy/mosquitto/mosquitto.conf):

```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

persistence true
persistence_location /var/lib/mosquitto/

log_dest file /var/log/mosquitto/mosquitto.log
```

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd livinglab
sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto
```

Uji:

```bash
mosquitto_sub -h localhost -u livinglab -P '<password>' -t 'smartgreengarden/#' -v
```

## 4. MariaDB

```bash
sudo mysql_secure_installation
sudo mysql <<'SQL'
CREATE DATABASE IF NOT EXISTS db_romy
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'romy'@'localhost' IDENTIFIED BY 'change_me';
GRANT SELECT, INSERT, UPDATE, DELETE ON db_romy.* TO 'romy'@'localhost';
FLUSH PRIVILEGES;
SQL

mysql -u root -p < /home/livinglab/workspace/romy/db/schema.sql
```

Biarkan MariaDB hanya bind ke `127.0.0.1`. Semua layanan berjalan di Pi yang sama.

## 5. Lingkungan Python

Satu venv untuk kedua layanan:

```bash
cd /home/livinglab/workspace/romy
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r services/data-logger/requirements.txt
.venv/bin/pip install -r services/telegram-bot/requirements.txt
```

Konfigurasi:

```bash
cp .env.example .env
nano .env            # isi kredensial sebenarnya
chmod 600 .env
```

> `.env` diabaikan git. Jangan pernah commit. Jika pernah ter-commit, ganti token Telegram, password DB, dan key Firebase.

## 6. Jalankan manual (tes pertama)

Sebelum memakai systemd, buktikan layanan bisa start:

```bash
cd /home/livinglab/workspace/romy
scripts/run_services.sh
```

Kedua layanan menulis log ke console dengan prefiks `[service]`. `Ctrl-C` menghentikan keduanya. Setelah ini berhasil, beralih ke systemd.

## 7. Unit systemd

`/etc/systemd/system/data-logger.service`:

```ini
[Unit]
Description=Living Lab data logger
After=network-online.target mariadb.service mosquitto.service
Wants=network-online.target
Requires=mariadb.service

[Service]
Type=simple
User=livinglab
WorkingDirectory=/home/livinglab/workspace/romy/services/data-logger
EnvironmentFile=/home/livinglab/workspace/romy/.env
ExecStart=/home/livinglab/workspace/romy/.venv/bin/python dataSave.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/telegram-bot.service` sama kecuali `Description`, `WorkingDirectory` (`services/telegram-bot`), dan `ExecStart` (`telegrambot.py`).

Salinan siap pakai: [`deploy/systemd/`](../deploy/systemd/). Sesuaikan path di sana bila root proyek Anda berbeda.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now data-logger telegram-bot
sudo systemctl status data-logger telegram-bot
```

## 8. Log

Ada dua tujuan log. Gunakan keduanya saat debugging:

```bash
# stdout/stderr systemd
journalctl -u data-logger -f
journalctl -u telegram-bot -n 100 --no-pager

# file log aplikasi (rotasi harian, gzip)
tail -f /home/livinglab/workspace/romy/services/data-logger/logs/garden.log
ls   /home/livinglab/workspace/romy/services/telegram-bot/logs/
```

`LOG_DIR` di `.env` menimpa lokasi default.

## 9. Backup

```bash
crontab -u livinglab -e
```

```cron
15 2 * * * /home/livinglab/workspace/romy/scripts/backup_db.sh
30 3 * * * mysql db_romy -e "DELETE FROM hydroponic_water_data_romy WHERE datetime < NOW() - INTERVAL 180 DAY;"
```

`backup_db.sh` menulis ke `/var/backups/livinglab` secara default (ubah dengan `BACKUP_DIR`). Set `BACKUP_DIR=/home/livinglab/workspace/romy/backups` bila user `livinglab` tidak bisa menulis ke `/var/backups`.

## 10. Checklist verifikasi

```bash
# 1. Broker jalan
systemctl is-active mosquitto

# 2. DB bisa diakses dan berisi baris
mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"

# 3. Layanan hidup
systemctl is-active data-logger telegram-bot

# 4. Ada node yang publish
mosquitto_sub -t 'smartgreengarden/#' -v
```

Jika keempatnya lolos, pipeline hidup dari ujung ke ujung. Lalu kirim `/status` ke bot.

## 11. Prosedur update

```bash
cd /home/livinglab/workspace/romy
git pull
.venv/bin/pip install -r services/data-logger/requirements.txt
.venv/bin/pip install -r services/telegram-bot/requirements.txt
sudo systemctl restart data-logger telegram-bot
journalctl -u data-logger -u telegram-bot -n 30 --no-pager
```

Periksa `db/migrations/` untuk file baru dan terapkan berurutan sebelum restart.

## 12. Catatan khusus Pi ini

| Item | Detail |
|---|---|
| Kredensial Firebase | `FIREBASE_CRED_PATH` menunjuk JSON service account; simpan di luar git |
| Export CSV | Ditulis di `EXPORT_DIR` lalu dihapus setelah bot mengirimnya |
| Kode proyek lain | Folder yang sama memuat catatan/kode lain — repo ini hanya memiliki `services/` |
| Tanpa container | Semua berjalan dari `.venv`; tidak ada langkah Docker/compose |