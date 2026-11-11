# Troubleshooting

[English](troubleshooting.md) | [Bahasa Indonesia](troubleshooting.id.md)

Periksa dari atas ke bawah: **device → broker → layanan → database → bot**. Lapisan pertama yang gagal adalah sumber masalahnya.

## 1. Apakah device benar-benar mengirim data?

```bash
mosquitto_sub -t 'smartgreengarden/#' -v
```

| Hasil | Arti | Langkah |
|---|---|---|
| Tidak ada apa pun | Tidak ada device terhubung, atau host/broker salah | Cek serial monitor, kredensial WiFi |
| Ada pesan `data` | Device baik — masalah di hilir | Lanjut ke §3 |
| Hanya `status` | Pembacaan sensor gagal | Cek wiring dan pin `#define` |
| Ada data tapi nilai salah | Bug kalibrasi / satuan | Bandingkan dengan multimeter atau referensi |

Serial monitor alat tercepat: `pio device monitor -b 115200`.

## 2. Apakah broker sehat?

```bash
systemctl status mosquitto
sudo mosquitto_sub -h localhost -t '$SYS/#' -v       # internal broker
sudo tail -n 50 /var/log/mosquitto/mosquitto.log
```

| Gejala | Penyebab | Solusi |
|---|---|---|
| `Connection refused` | Broker tidak jalan | `sudo systemctl restart mosquitto` |
| `Connection refused` dari mesin lain | `listener` hanya bind localhost | Cek `/etc/mosquitto/conf.d/*.conf` |
| `Not authorized` | Username/password salah | Buat ulang dengan `mosquitto_passwd` |
| Lokal bisa, ESP32 tidak | Firewall atau WiFi 5 GHz | ESP hanya 2.4 GHz; buka port 1883 |

## 3. Apakah layanan Python jalan?

```bash
systemctl status data-logger telegram-bot
journalctl -u data-logger -n 100 --no-pager
```

| Gejala | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError` | venv tidak dipakai / dependensi kurang | `.venv/bin/pip install -r services/<svc>/requirements.txt` |
| `KeyError: 'MQTT_HOST'` | `.env` tidak dimuat atau key hilang | `EnvironmentFile=` pada unit, atau salin dari `.env.example` |
| Crash berulang, `Restart=always` | Exception tak tertangani saat start | Baca traceback pertama: `journalctl -u <svc> -n 30` |
| Status "active" tapi diam | Topik salah / tidak pernah menerima pesan | Pastikan client id dan `MQTT_TOPIC_PREFIX` |

Jalankan layanan manual untuk melihat output langsung:

```bash
cd services/data-logger
set -a; source ../../.env; set +a
../../.venv/bin/python main.py
```

## 4. Apakah data masuk MariaDB?

```bash
mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"
mysql -u romy -p -e "SELECT * FROM db_romy.hydroponic_water_data_romy ORDER BY id DESC LIMIT 5;"
```

| Gejala | Penyebab | Solusi |
|---|---|---|
| `COUNT(*)` tetap 0 | Logger tidak subscribe, atau insert gagal diam-diam | Cek log logger untuk error SQL |
| `Cannot add or update a child row` (FK) | Skema ini tidak punya foreign key — error berarti Anda mengubah `db/schema.sql` secara lokal | Pakai skema di repo tanpa perubahan |
| `Data too long` / `Incorrect decimal value` | Field payload di luar jangkauan atau tipe salah | Cek batas DECIMAL di `docs/database.id.md` |
| Insert melambat setelah berbulan-bulan | Tabel besar, tidak ada index pada `datetime` | Pastikan `idx_sensor_datetime`; terapkan retensi |
| `Access denied for user` | Kredensial DB salah atau grant host salah | `GRANT ... TO 'romy'@'localhost'` |

## 5. Apakah bot merespons?

| Gejala | Penyebab | Solusi |
|---|---|---|
| Tidak ada balasan | Layanan mati atau token salah | `journalctl -u telegram-bot -n 50`; uji `getMe` di browser |
| Balas "not authorized" | Chat id tidak ada di allow-list | Tambahkan ke `TELEGRAM_ALLOWED_CHAT_IDS`, restart |
| Alert tidak muncul | Tidak ada baris alert, atau logika `notified_at` | `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |

## 6. Masalah umum ESP32 / Wemos

| Gejala | Penyebab | Solusi |
|---|---|---|
| Boot loop, `Brownout detector` | Arus kurang | PSU lebih baik / kapasitor dekat 3V3 |
| Tidak bisa konek WiFi | Jaringan 5 GHz, atau SSID salah | Pakai 2.4 GHz; cek ulang kredensial |
| `Connection reset by peer` pada MQTT | Client id bentrok (dua board, id sama) | Buat `device_id` unik per board |
| Jalan, lalu mati setelah beberapa jam | Memory leak / tanpa logika reconnect | Cek loop reconnect; pantau free heap di serial |
| Karakter aneh di log serial | Baud rate salah | Samakan `monitor_speed` di `platformio.ini` |

## 7. Level WiFi / sistem Pi

```bash
ip addr show wlan0
iwconfig wlan0 | grep -i quality
df -h                   # disk penuh membuat MariaDB bermasalah
dmesg | tail -30        # peringatan undervoltage
vcgencmd measure_temp   # suhu Pi
```

| Gejala | Penyebab | Solusi |
|---|---|---|
| Pi reboot acak | Undervoltage | Pakai PSU resmi; cek `dmesg` untuk `voltage` |
| MariaDB "disk full" | Log/readings tanpa batas | Job retensi + rotasi log |
| Semua mati setelah reboot | Layanan tidak di-enable | `systemctl enable mosquitto mariadb data-logger telegram-bot` |

## 8. Reset menyeluruh (hanya mesin lab)

```bash
sudo systemctl stop data-logger telegram-bot
sudo systemctl restart mosquitto mariadb
sudo systemctl start data-logger telegram-bot
```

Baru lakukan setelah tiga syarat dasar lolos: broker `is-active`, `mosquitto_sub` menunjukkan trafik, `SELECT COUNT(*)` bertambah.

## Masih macet?

Kumpulkan ini sebelum bertanya:

```bash
uname -a
systemctl status mosquitto mariadb data-logger telegram-bot --no-pager
journalctl -u data-logger -u data-logger -u telegram-bot -n 100 --no-pager
mysql -u romy -p -e "SELECT COUNT(*) FROM db_romy.hydroponic_water_data_romy;"
mosquitto_sub -t 'smartgreengarden/#' -v -W 5
```

TODO: tambahkan pesan error yang benar-benar Anda temui saat pengembangan — itu yang akan ditemui mahasiswa berikutnya.