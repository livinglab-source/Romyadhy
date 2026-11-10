# MQTT Bridge

[English](README.md) | [Bahasa Indonesia](README.id.md)

Subscribe `smartgreengarden/#`, validasi dan normalisasi payload, lalu teruskan reading bersih ke data logger.

- Bahasa: Python 3.11
- Unit: `deploy/systemd/mqtt-bridge.service`
- Bergantung pada: Mosquitto (`MQTT_*` di `.env`)

## Tanggung jawab

- Subscribe `smartgreengarden/+/data` dan `smartgreengarden/+/status`
- Tolak payload cacat (field hilang, nilai di luar jangkauan, `schema` salah)
- Normalisasi satuan dan tipe sebelum diteruskan
- Log peringatan berisi payload mentah saat validasi gagal

**Tidak** menulis ke database dan **tidak** memanggil Telegram.

## Konfigurasi

| Key | Arti |
|---|---|
| `MQTT_HOST` / `MQTT_PORT` | Alamat broker |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | Kredensial broker |
| `MQTT_TOPIC_PREFIX` | Default `livinglab` |
| `LOG_LEVEL` | `INFO` normal, `DEBUG` saat memvalidasi payload |

## Jalankan

```bash
cd services/mqtt-bridge
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Debug

```bash
mosquitto_sub -t 'smartgreengarden/#' -v          # ada pesan masuk?
journalctl -u mqtt-bridge -f               # di Pi
```

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Start lalu keluar | Env var hilang | `KeyError` di log — cek `.env` |
| Tidak ada pesan | Prefix atau kredensial salah | Cek `MQTT_TOPIC_PREFIX`, uji dengan `mosquitto_sub` |
| Semua ditolak | `schema` tidak cocok dengan firmware | Samakan dengan [../../docs/mqtt-topics.id.md](../../docs/mqtt-topics.id.md) |