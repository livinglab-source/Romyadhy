# Deployment (Raspberry Pi)

[English](deployment.md) | [Bahasa Indonesia](deployment.id.md)

Target: Raspberry Pi OS, Mosquitto, MariaDB, and the Python services run from a venv on the Pi.

**No Docker.** The services run directly from a virtualenv, and are kept alive by systemd.

## Paths used

| Item | Path |
|---|---|
| Project root | `/home/livinglab/workspace/romy` |
| Virtualenv | `/home/livinglab/workspace/romy/.venv` |
| Config | `/home/livinglab/workspace/romy/.env` |
| Service code | `/home/livinglab/workspace/romy/services/` |
| Backups | `/var/backups/livinglab` |

> The Pi also holds other project notes and code under `/home/livinglab/workspace/romy`. This repository documents the IoT pipeline only; refer to those local notes for the rest.

## 1. Prerequisites

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients mariadb-server python3-venv python3-pip git
```

## 2. Get the code

```bash
cd /home/livinglab/workspace
git clone <repo-url> romy
cd romy
```

If the folder already exists, this is an update: `git pull` (see §10).

## 3. Mosquitto

`/etc/mosquitto/conf.d/livinglab.conf` — a copy is kept at [`deploy/mosquitto/mosquitto.conf`](../deploy/mosquitto/mosquitto.conf):

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

Test:

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

Leave MariaDB bound to `127.0.0.1`. All services run on the same Pi.

## 5. Python environment

One venv serves both services:

```bash
cd /home/livinglab/workspace/romy
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r services/data-logger/requirements.txt
.venv/bin/pip install -r services/telegram-bot/requirements.txt
```

Config:

```bash
cp .env.example .env
nano .env            # fill in real credentials
chmod 600 .env
```

> `.env` is git-ignored. Never commit it. If it was ever committed, rotate the Telegram token, DB password, and Firebase key.

## 6. Run by hand (first test)

Before wiring systemd, prove the services start:

```bash
cd /home/livinglab/workspace/romy
scripts/run_services.sh
```

Both services log to the console with a `[service]` prefix. `Ctrl-C` stops them. Once this works, switch to systemd.

## 7. systemd units

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

`/etc/systemd/system/telegram-bot.service` is identical except `Description`, `WorkingDirectory` (`services/telegram-bot`), and `ExecStart` (`telegrambot.py`).

Ready-made copies: [`deploy/systemd/`](../deploy/systemd/). Update the paths there if your project root differs.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now data-logger telegram-bot
sudo systemctl status data-logger telegram-bot
```

## 8. Logs

Two log destinations exist. Use both when debugging:

```bash
# systemd stdout/stderr
journalctl -u data-logger -f
journalctl -u telegram-bot -n 100 --no-pager

# application log files (daily rotation, gzipped)
tail -f /home/livinglab/workspace/romy/services/data-logger/logs/garden.log
ls   /home/livinglab/workspace/romy/services/telegram-bot/logs/
```

`LOG_DIR` in `.env` overrides the default location.

## 9. Backups

```bash
crontab -u livinglab -e
```

```cron
15 2 * * * /home/livinglab/workspace/romy/scripts/backup_db.sh
30 3 * * * mysql db_romy -e "DELETE FROM hydroponic_water_data_romy WHERE datetime < NOW() - INTERVAL 180 DAY;"
```

`backup_db.sh` writes to `/var/backups/livinglab` by default (override with `BACKUP_DIR`). Set `BACKUP_DIR=/home/livinglab/workspace/romy/backups` if `livinglab` cannot write to `/var/backups`.

## 10. Verification checklist

```bash
# 1. Broker running
systemctl is-active mosquitto

# 2. DB reachable and has rows
mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"

# 3. Services up
systemctl is-active data-logger telegram-bot

# 4. A node publishes
mosquitto_sub -t 'smartgreengarden/#' -v
```

If all four pass, the pipeline is alive end to end. Then send `/status` to the bot.

## 11. Update procedure

```bash
cd /home/livinglab/workspace/romy
git pull
.venv/bin/pip install -r services/data-logger/requirements.txt
.venv/bin/pip install -r services/telegram-bot/requirements.txt
sudo systemctl restart data-logger telegram-bot
journalctl -u data-logger -u telegram-bot -n 30 --no-pager
```

Check `db/migrations/` for new files and apply them in order before restarting.

## 12. Notes specific to this Pi

| Item | Detail |
|---|---|
| Firebase credentials | `FIREBASE_CRED_PATH` points at the service-account JSON; keep it outside git |
| CSV exports | Written under `EXPORT_DIR` then deleted after the bot sends them |
| Other project code | The same folder holds unrelated notes/code — this repo owns `services/` only |
| No containers | Everything runs from `.venv`; there is no Docker/compose step |