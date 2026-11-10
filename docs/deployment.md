# Deployment (Raspberry Pi)

[English](deployment.md) | [Bahasa Indonesia](deployment.id.md)

Target: Raspberry Pi OS (64-bit), Mosquitto, MariaDB, three Python services started by systemd.

## 1. Prerequisites

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients mariadb-server python3-venv python3-pip git
```

## 2. Users and directories

```bash
# Dedicated user for the services (no login shell)
sudo useradd --system --create-home --shell /usr/sbin/nologin livinglab

# Code location
sudo mkdir -p /opt/livinglab
sudo chown livinglab:livinglab /opt/livinglab
sudo -u livinglab git clone <repo-url> /opt/livinglab/Romyadhy

# Backup location
sudo mkdir -p /var/backups/livinglab
sudo chown livinglab:livinglab /var/backups/livinglab
```

## 3. Mosquitto

`/etc/mosquitto/conf.d/livinglab.conf`:

```conf
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Persist messages across restarts
persistence true
persistence_location /var/lib/mosquitto/

log_dest file /var/log/mosquitto/mosquitto.log
```

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd livinglab
sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto
```

Test:

```bash
mosquitto_sub -h localhost -u livinglab -P '<password>' -t 'smartgreengarden/#' -v
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

Bind address: leave MariaDB on `127.0.0.1` only. Services run on the same Pi.

## 5. Python environment

One shared venv is simplest for three small services:

```bash
cd /opt/livinglab/Romyadhy
sudo -u livinglab python3 -m venv .venv
sudo -u livinglab .venv/bin/pip install --upgrade pip
sudo -u livinglab .venv/bin/pip install -r services/data-logger/requirements.txt
sudo -u livinglab .venv/bin/pip install -r services/data-logger/requirements.txt
sudo -u livinglab .venv/bin/pip install -r services/telegram-bot/requirements.txt
```

Config:

```bash
sudo -u livinglab cp .env.example .env
sudo -u livinglab nano .env          # fill in real credentials
sudo chmod 600 .env
```

> `.env` is git-ignored. Never commit it. If it was ever committed, rotate the Telegram token and DB password.

## 6. systemd units

Example `/etc/systemd/system/data-logger.service`:

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

Repeat for `telegram-bot` (change `Description`, `WorkingDirectory`, `ExecStart`, and `After` as needed). The unit is already provided in `deploy/systemd/`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now data-logger telegram-bot
sudo systemctl status data-logger telegram-bot
```

Templates live in [`deploy/systemd/`](../deploy/systemd/).

## 7. Logs

```bash
journalctl -u data-logger -f
journalctl -u data-logger -f --since "10 min ago"
journalctl -u telegram-bot -n 100 --no-pager
```

## 8. Backups

```bash
sudo crontab -u livinglab -e
```

```cron
15 2 * * * /opt/livinglab/Romyadhy/scripts/backup_db.sh
30 3 * * * mysql livinglab -e "DELETE FROM readings WHERE recorded_at < NOW() - INTERVAL 90 DAY;"
```

## 9. Verification checklist

```bash
# 1. Broker running
systemctl is-active mosquitto

# 2. DB reachable
mysql -u livinglab -p -e "SELECT COUNT(*) FROM livinglab.readings;"

# 3. Services up
systemctl is-active data-logger telegram-bot

# 4. A node publishes
mosquitto_sub -t 'smartgreengarden/#' -v
```

If all four pass, the pipeline is alive end to end.

## 10. Update procedure

```bash
cd /opt/livinglab/Romyadhy
sudo -u livinglab git pull
sudo -u livinglab .venv/bin/pip install -r services/*/requirements.txt
sudo systemctl restart data-logger telegram-bot
```

Check `db/migrations/` for new files and apply them in order before restarting.