# Documentation Index

[English](README.md) | [Bahasa Indonesia](README.id.md)

> Versi Inggris adalah acuan utama. Terjemahan Bahasa Indonesia bisa tertinggal.
> Jika ada perbedaan, file berbahasa Inggris yang dianggap benar.

## Mulai dari sini

| # | Dokumen | Baca ketika |
|---|---|---|
| 1 | [onboarding.id.md](onboarding.id.md) | Baru clone repo dan ingin menjalankannya |
| 2 | [architecture.id.md](architecture.id.md) | Butuh gambaran besar / alur data |
| 3 | [deployment.id.md](deployment.id.md) | Sedang menyiapkan Raspberry Pi |
| 4 | [troubleshooting.id.md](troubleshooting.id.md) | Ada yang tidak berjalan |

> **Cakupan.** Repo ini mendokumentasikan pipeline IoT: firmware, dua layanan Python, kontrak MQTT, dan database. Di Raspberry Pi juga tersimpan catatan dan kode proyek lain di `/home/livinglab/workspace/romy`; baca itu untuk hal yang tidak tercakup di sini.

## Referensi

| Dokumen | Isi |
|---|---|
| [hardware.md](hardware.md) | Daftar komponen (BOM), wiring, pinout, pemetaan board → peran |
| [mqtt-topics.md](mqtt-topics.md) | Penamaan topik, QoS/retain, kontrak payload JSON |
| [database.md](database.md) | Skema MariaDB, diagram ER, index, retensi, backup |
| [telegram-bot.md](telegram-bot.md) | Perintah bot, setup token, chat id yang diizinkan |

## Terjemahan

| English | Bahasa Indonesia |
|---|---|
| [architecture.md](architecture.md) | [architecture.id.md](architecture.id.md) |
| [deployment.md](deployment.md) | [deployment.id.md](deployment.id.md) |
| [troubleshooting.md](troubleshooting.md) | [troubleshooting.id.md](troubleshooting.id.md) |
| [onboarding.md](onboarding.md) | [onboarding.id.md](onboarding.id.md) |
| [mqtt-topics.md](mqtt-topics.md) | [mqtt-topics.id.md](mqtt-topics.id.md) |

## Konvensi

- Diagram ditulis dengan **Mermaid** di dalam Markdown agar tersimpan bersama kode.
- Perintah selalu dalam blok `bash` dan bisa langsung di-copy-paste.
- Rahasia (token, password) tidak pernah ditulis di dokumen. Sebutkan nama key saja lewat `.env.example`.
- Setiap folder komponen punya `README.md` dengan urutan bagian yang sama.