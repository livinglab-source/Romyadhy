# Telegram Bot

[English](telegram-bot.md) | [Bahasa Indonesia](telegram-bot.id.md)

Kode: [`services/telegram-bot/`](../services/telegram-bot/)

## Fungsi

Dua arah:

1. **Keluar** — mengirim alert (melewati ambang batas, device offline) ke chat Telegram.
2. **Masuk** — menjawab perintah dengan query MariaDB atau publish perintah MQTT.

## Setup

1. Buka [@BotFather](https://t.me/BotFather) → `/newbot` → salin token.
2. Masukkan ke `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

3. Cari chat id Anda: kirim pesan ke bot, lalu buka
   `https://api.telegram.org/bot<TOKEN>/getUpdates` dan baca `message.chat.id`.
4. **Selalu isi `TELEGRAM_ALLOWED_CHAT_IDS`.** Tanpa itu, siapa pun yang menemukan bot bisa memberi perintah ke device Anda.

## Perintah

| Perintah | Contoh | Hasil |
|---|---|---|
| `/start` | `/start` | Bantuan singkat |
| `/status <device>` | `/status esp32-01` | Online/offline, RSSI, terakhir terlihat |
| `/last <device>` | `/last esp32-01` | Reading terbaru |
| `/avg <device> <jam>` | `/avg esp32-01 24` | Rata-rata suhu/kelembapan |
| `/devices` | `/devices` | Daftar device terdaftar |
| `/relay <device> <0\|1>` | `/relay wemos-01 1` | Publish `cmd` MQTT |
| `/alert <suhu> <kelembapan>` | `/alert 30 80` | Set ambang batas (TODO: disimpan di mana?) |

TODO: cocokkan daftar perintah ini dengan kode yang benar-benar dibuat, lalu hapus baris yang tidak ada.

## Aturan alert

| Aturan | Pemicu | Cooldown |
|---|---|---|
| Suhu tinggi | `temp_c > ambang` | `ALERT_COOLDOWN_SECONDS` |
| Device offline | `last_seen` lebih lama dari N menit | sekali per transisi |

Cooldown mencegah banjir pesan: satu notifikasi per aturan per jendela cooldown, bukan per pesan.

Bot mengambil pekerjaan dari tabel `alerts`:

```sql
SELECT id, device_id, kind, message
FROM alerts WHERE notified_at IS NULL ORDER BY created_at LIMIT 20;
```

lalu set `notified_at = NOW(3)` setelah berhasil terkirim. Pengiriman yang gagal membuat baris tetap pending — retry tidak perlu kode baru.

## Catatan keamanan

- Token hanya di `.env`, tidak pernah di kode atau dokumen.
- Daftar chat id yang diizinkan adalah satu-satunya otorisasi — tidak ada peran per pengguna.
- Jika token bocor: `/revoke` di BotFather, buat token baru, update `.env`, restart layanan.
- Jangan log respons API penuh di level `INFO`; URL-nya mengandung token.

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Bot diam | Layanan mati | `systemctl status telegram-bot`, `journalctl -u telegram-bot -n 50` |
| `401 Unauthorized` | Token salah/dicabut | Cek ulang `.env`, restart |
| Perintah diabaikan | Chat id Anda tidak ada di `TELEGRAM_ALLOWED_CHAT_IDS` | Tambahkan, restart |
| Alert tidak pernah masuk | `notified_at` tidak pernah NULL / tidak ada baris alert | Cek aturan alert di bridge, lalu `SELECT * FROM alerts ORDER BY id DESC LIMIT 5;` |