# Troubleshooting

[English](troubleshooting.md) | [Bahasa Indonesia](troubleshooting.id.md)

Work top-down: **device → broker → service → database → bot**. The first layer that fails is your problem.

## 1. Is the device even publishing?

```bash
mosquitto_sub -t 'livinglab/#' -v
```

| Result | Meaning | Next step |
|---|---|---|
| Nothing at all | No device connected, or wrong broker/host | Check serial monitor, WiFi credentials |
| `data` messages | Device is fine — problem is downstream | Go to §3 |
| Only `status` | Sensor read failing | Check wiring and `#define` pins |
| Data but wrong values | Calibration / unit bug | Compare against a multimeter or known reference |

Serial monitor is the fastest tool: `pio device monitor -b 115200`.

## 2. Is the broker healthy?

```bash
systemctl status mosquitto
sudo mosquitto_sub -h localhost -t '$SYS/#' -v       # broker internals
sudo tail -n 50 /var/log/mosquitto/mosquitto.log
```

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` | Broker not running | `sudo systemctl restart mosquitto` |
| `Connection refused` from another machine | `listener` bound to localhost only | Check `/etc/mosquitto/conf.d/*.conf` |
| `Not authorized` | Wrong username/password | Recreate with `mosquitto_passwd` |
| Works locally, not from ESP32 | Firewall or 5 GHz WiFi | ESP only supports 2.4 GHz; open port 1883 |

## 3. Are the Python services running?

```bash
systemctl status mqtt-bridge data-logger telegram-bot
journalctl -u mqtt-bridge -n 100 --no-pager
```

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | venv not used / deps missing | `sudo -u livinglab .venv/bin/pip install -r services/<svc>/requirements.txt` |
| `KeyError: 'MQTT_HOST'` | `.env` not loaded or missing key | `EnvironmentFile=` in unit, or copy from `.env.example` |
| Crash loop, `Restart=always` | Unhandled exception at startup | Read first traceback with `journalctl -u <svc> -n 30` |
| Service "active" but idle | Wrong topic / never receives messages | Confirm client id and `MQTT_TOPIC_PREFIX` |

Run a service by hand to see output live:

```bash
cd services/data-logger
set -a; source ../../.env; set +a
../../.venv/bin/python main.py
```

## 4. Is data reaching MariaDB?

```bash
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM readings;"
mysql -u livinglab -p livinglab -e "SELECT * FROM readings ORDER BY id DESC LIMIT 5;"
```

| Symptom | Cause | Fix |
|---|---|---|
| `COUNT(*)` stays 0 | Logger not subscribed, or insert failing silently | Check logger logs for SQL errors |
| `Cannot add or update a child row` (FK) | Device not registered in `devices` | `INSERT INTO devices (device_id, board_type, role) VALUES (...)` |
| `Data too long` / `Incorrect decimal value` | Payload field out of range or wrong type | Validate in the bridge; check `DECIMAL(5,2)` bounds |
| Inserts slow after months | Missing index / table huge | Confirm `idx_readings_device_time`; apply retention |
| `Access denied for user` | Wrong DB credentials or host grant | `GRANT ... TO 'livinglab'@'localhost'` |

## 5. Is the bot responding?

| Symptom | Cause | Fix |
|---|---|---|
| No reply | Service down or token wrong | `journalctl -u telegram-bot -n 50`; test `getMe` in a browser |
| Replies "not authorized" | Chat id missing from allow-list | Add to `TELEGRAM_ALLOWED_CHAT_IDS`, restart |
| Alerts missing | No alert rows, or `notified_at` logic | `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |

## 6. Common ESP32 / Wemos issues

| Symptom | Cause | Fix |
|---|---|---|
| Boot loop, `Brownout detector` | Insufficient current | Better PSU / add capacitor near 3V3 |
| Won't connect to WiFi | 5 GHz network, or wrong SSID | Use 2.4 GHz; recheck credentials |
| `Connection reset by peer` on MQTT | Client id collision (two boards, same id) | Make `device_id` unique per board |
| Works, then dies after hours | Memory leak / no reconnect logic | Check reconnect loop; watch free heap in serial |
| Wrong characters in serial log | Wrong baud rate | Match `monitor_speed` in `platformio.ini` |

## 7. Wifi / Pi system level

```bash
ip addr show wlan0
iwconfig wlan0 | grep -i quality
df -h                   # disk full breaks MariaDB
dmesg | tail -30        # undervoltage warnings
vcgencmd measure_temp   # Pi temperature
```

| Symptom | Cause | Fix |
|---|---|---|
| Random Pi reboots | Undervoltage | Official PSU; check `dmesg` for `voltage` |
| MariaDB "disk full" | Logs/readings unbounded | Retention job + log rotation |
| Everything fails after reboot | Services not enabled | `systemctl enable mosquitto mariadb mqtt-bridge data-logger telegram-bot` |

## 8. Nuclear reset (lab machine only)

```bash
sudo systemctl stop mqtt-bridge data-logger telegram-bot
sudo systemctl restart mosquitto mariadb
sudo systemctl start mqtt-bridge data-logger telegram-bot
```

Only after the three basics pass: broker `is-active`, `mosquitto_sub` shows traffic, `SELECT COUNT(*)` increases.

## Still stuck?

Collect these before asking for help:

```bash
uname -a
systemctl status mosquitto mariadb mqtt-bridge data-logger telegram-bot --no-pager
journalctl -u mqtt-bridge -u data-logger -u telegram-bot -n 100 --no-pager
mysql -u livinglab -p livinglab -e "SELECT COUNT(*) FROM readings;"
mosquitto_sub -t 'livinglab/#' -v -W 5
```

TODO: add the error messages you actually hit during development — those are the ones the next student will hit too.