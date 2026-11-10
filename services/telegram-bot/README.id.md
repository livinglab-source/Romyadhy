# Telegram Bot

[English](README.md) | [Bahasa Indonesia](README.id.md)

Mengirim alert dan menjawab perintah pengguna.

- Bahasa: Python 3.11
- Unit: `deploy/systemd/telegram-bot.service`
- Bergantung pada: MariaDB, Mosquitto, Telegram Bot API

## Tanggung jawab

- Polling Telegram untuk perintah lalu membalas
- Query MariaDB untuk `/status`, `/last`, `/avg`, `/devices`
- Publish pesan MQTT `cmd` untuk `/relay`
- Mengirim alert pending dari tabel `alerts`, lalu set `notified_at`

Referensi perintah dan catatan keamanan: [../../docs/telegram-bot.id.md](../../docs/telegram-bot.id.md)

## Konfigurasi

| Key | Arti |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Dari @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Allow-list dipisah koma — **wajib** |
| `DB_*` | Kredensial MariaDB |
| `MQTT_*` | Alamat broker |
| `ALERT_COOLDOWN_SECONDS` | Jarak minimum antar alert berulang |

## Jalankan

```bash
cd services/telegram-bot
pip install -r requirements.txt
set -a; source ../../.env; set +a
python main.py
```

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Tidak ada balasan | Layanan mati / token salah | `journalctl -u telegram-bot -n 50`; uji `getMe` |
| `401 Unauthorized` | Token dicabut | Token baru dari BotFather, update `.env`, restart |
| Perintah diabaikan | Chat id tidak diizinkan | Tambahkan ke `TELEGRAM_ALLOWED_CHAT_IDS`, restart |
| Alert tidak terkirim | `notified_at` tidak pernah NULL / tidak ada baris | `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |