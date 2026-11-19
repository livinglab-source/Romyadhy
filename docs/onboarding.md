# Onboarding (Clone → Running)

[English](onboarding.md) | [Bahasa Indonesia](onboarding.id.md)

For a new contributor. Follow in order; do not skip the checks.

## 0. What you need

| Item | Notes |
|---|---|
| Linux / macOS / WSL | Windows: use WSL, not native CMD |
| Python 3.11+ | `python3 --version` |
| Git | |
| Access to the lab WiFi (2.4 GHz) | For real devices |
| `.env` values | Ask the lab admin — they are not in git |

Optional for firmware: PlatformIO Core (`pip install platformio`) or VS Code + PlatformIO extension.

## 1. Get the code

```bash
git clone <repo-url> Romyadhy
cd Romyadhy
```

## 2. Read in this order (15 min)

1. [README.md](../README.md) — what the system is
2. [architecture.md](architecture.md) — how the pieces talk
3. [mqtt-topics.md](mqtt-topics.md) — the contract
4. The README of the component you will touch

## 3. Configure

```bash
cp .env.example .env
# edit .env: MQTT_HOST, DB_*, TELEGRAM_BOT_TOKEN
```

Never commit `.env`. Confirm it is ignored:

```bash
git check-ignore -v .env    # should print .gitignore:<line>:.env
```

## 4. Broker and database

This project does not use Docker. Two cases:

**A — you work on the Pi (normal case):** Mosquitto and MariaDB are already installed and running. Set `MQTT_HOST=127.0.0.1` and `DB_HOST=127.0.0.1` in `.env`, then go to §5.

**B — you develop on your own machine:** install and start them locally.

```bash
sudo apt install mosquitto mosquitto-clients mariadb-server
sudo systemctl start mosquitto mariadb
mysql -u root -p < db/schema.sql
```

## 5. Python services

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/data-logger/requirements.txt
pip install -r services/telegram-bot/requirements.txt

scripts/run_services.sh
```

## 6. Firmware (only if you have a board)

Firmware sketches (`.ino`) can be flashed via Arduino IDE or PlatformIO:

- **ESP32 Sensor Node:** `firmware/esp32-sensor-node/keren-12.ino`
- **Wemos Water Level A:** `firmware/wemos-gateway/wemos_a_waterlevel_code.ino`
- **Wemos Water Level B:** `firmware/wemos-gateway/wemos_b_waterlevel_code.ino`

Set WiFi credentials (`ssid`, `password`) and MQTT broker IP (`mqtt_server`) at the top of each sketch before flashing.

## 7. Verify end to end

Run these in four terminals:

```bash
# 1. Watch MQTT
mosquitto_sub -t 'smartgreengarden/#' -v

# 2. Watch the logger
journalctl -u data-logger -f          # or the run_services.sh output

# 3. Watch the DB
watch -n 5 'mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"'

# 4. Talk to the bot
#    send /status esp32-01 in Telegram
```

Success = a new MQTT message appears **and** the DB count increases **and** the bot answers.

## 8. Make your first change

```bash
git switch -c feat/your-change
# edit
git add <files>
git commit -m "feat(component): short description"
git push -u origin feat/your-change
```

Open a PR. Do not push directly to `main`.

## 9. Where to look when stuck

| Need | Go to |
|---|---|
| Data not flowing | [troubleshooting.md](troubleshooting.md) §1–§2 |
| Service crashing | [troubleshooting.md](troubleshooting.md) §3 |
| DB errors | [troubleshooting.md](troubleshooting.md) §4 |
| Pi setup from scratch | [deployment.md](deployment.md) |
| Payload shape | [mqtt-topics.md](mqtt-topics.md) |

## Checklist

- [ ] `.env` created and ignored by git
- [ ] Broker reachable (`mosquitto_sub` shows a message)
- [ ] Schema applied (`SELECT COUNT(*) FROM hydroponic_water_data_romy` works)
- [ ] Three services start without traceback
- [ ] At least one reading reaches MariaDB
- [ ] Bot replies to `/start`

TODO: add the lab admin contact and the actual repo URL.