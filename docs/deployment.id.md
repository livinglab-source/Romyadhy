# Deployment (Raspberry Pi)

[English](deployment.md) | [Bahasa Indonesia](deployment.id.md)

Target: Raspberry Pi OS (64-bit), Mosquitto, MariaDB, tiga layanan Python dijalankan oleh systemd.

## 1. Prasyarat

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients mariadb-server python3-venv python3-pip git
```

## 2. User dan direktori

```bash
# User khusus untuk layanan (tanpa shell login)
sudo useradd --system --create-home --shell /usr/sbin/nologin livinglab

# Lokasi kode
sudo mkdir -p /opt/livinglab
sudo chown livinglab:livinglab /opt/livinglab
sudo -u livinglab git clone <repo-url> /opt/livinglab/Romyadhy

# Lokasi backup
sudo mkdir -p /var/backups/livinglab
sudo chown livinglab:livinglab /var/backups/livinglab
```

## 3. Mosquitto

`/etc/mosquitto/conf.d/livinglab.conf`:

```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Pesan tetap tersimpan setelah restart
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
mosquitto_sub -h localhost -u livinglab -P '<password>' -t 'livinglab/#' -v
```

## 4. MariaDB

```bash
sudo mysql_secure_installation
sudo mysql <<'SQL'
CREATE DATABASE IF NOT EXISTS livinglab
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'livinglab'@'localhost' IDENTIFIED BY 'change_me';
GRANT SELECT, INSERT, UPDATE, DELETE ON livinglab.* TO 'livinglab'@'localhost';
FLUSH PRIVILEGES;
SQL

mysql -u root -p < /opt/livinglab/Romyadhy/db/schema.sql
```

Bind address: biarkan MariaDB hanya di `127.0.0.1`. Semua layanan berjalan di Pi yang sama.

## 5. Lingkungan Python

Satu venv bersama paling sederhana untuk tiga layanan kecil:

```bash
cd /opt/livinglab/Romyadhy
sudo -u livinglab python3 -m venv .venv
sudo -u livinglab .venv/bin/pip install --upgrade pip
sudo -u livinglab .venv/bin/pip install -r services/mqtt-bridge/requirements.txt
sudo -u livinglab .venv/bin/pip install -r services/data-logger/requirements.txt
sudo -u livinglab .venv/bin/pip install -r services/telegram-bot/requirements.txt
```

Konfigurasi:

```bash
sudo -u livinglab cp .env.example .env
sudo -u livinglab nano .env          # isi kredensial sebenarnya
sudo chmod 600 .env
```

> `.env` diabaikan git. Jangan pernah commit. Jika pernah ter-commit, ganti token Telegram dan password DB.

## 6. Unit systemd

Contoh `/etc/systemd/system/data-logger.service`:

```ini
[Unit]
Description=Living Lab data logger
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=livinglab
WorkingDirectory=/opt/livinglab/Romyadhy/services/data-logger
EnvironmentFile=/opt/livinglab/Romyadhy/.env
ExecStart=/opt/livinglab/Romyadhy/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Ulangi untuk `mqtt-bridge` dan `telegram-bot` (ubah `Description`, `WorkingDirectory`, `ExecStart`, dan `After` bila perlu — bot sebaiknya start setelah `mqtt-bridge`).

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mqtt-bridge data-logger telegram-bot
sudo systemctl status mqtt-bridge data-logger telegram-bot
```

Template tersedia di [`deploy/systemd/`](../deploy/systemd/).

## 7. Log

```bash
journalctl -u data-logger -f
journalctl -u mqtt-bridge -f --since "10 min ago"
journalctl -u telegram-bot -n 100 --no-pager
```

## 8. Backup

```bash
sudo crontab -u livinglab -e
```

```cron
15 2 * * * /opt/livinglab/Romyadhy/scripts/backup_db.sh
30 3 * * * mysql livinglab -e "DELETE FROM readings WHERE recorded_at < NOW() - INTERVAL 90 DAY;"
```

## 9. Checklist verifikasi

```bash
# 1. Broker jalan
systemctl is-active mosquitto

# 2. DB bisa diakses
mysql -u livinglab -p -e "SELECT COUNT(*) FROM livinglab.readings;"

# 3. Layanan hidup
systemctl is-active mqtt-bridge data-logger telegram-bot

# 4. Ada node yang publish
mosquitto_sub -t 'livinglab/#' -v
```

Jika keempatnya lolos, pipeline hidup dari ujung ke ujung.

## 10. Prosedur update

```bash
cd /opt/livinglab/Romyadhy
sudo -u livinglab git pull
sudo -u livinglab .venv/bin/pip install -r services/*/requirements.txt
sudo systemctl restart mqtt-bridge data-logger telegram-bot
```

Periksa `db/migrations/` untuk file baru dan terapkan berurutan sebelum restart.