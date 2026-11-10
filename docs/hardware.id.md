# Perangkat Keras

[English](hardware.md) | [Bahasa Indonesia](hardware.id.md)

> Nama folder menunjukkan **peran**. Tabel ini memetakan peran ke board yang dipakai.

## Pemetaan board → peran

| Peran | Board | Folder | Device id (MQTT) |
|---|---|---|---|
| Node sensor | ESP32 (TODO: model persis, mis. DevKit V1) | `firmware/esp32-sensor-node` | `esp32-01` |
| Gateway / relay | Wemos D1 mini (ESP8266) | `firmware/wemos-gateway` | `wemos-01` |
| Broker + layanan | Raspberry Pi (TODO: model / RAM / OS) | `services/`, `deploy/` | — |

TODO: konfirmasi perannya. Jika ESP32 yang menjadi gateway dan Wemos menjadi node sensor, tukar baris di atas dan ganti nama foldernya.

## Daftar komponen (BOM)

| Jumlah | Item | Catatan |
|---|---|---|
| 1 | Board development ESP32 | TODO: varian persis |
| 1 | Wemos D1 mini | Berbasis ESP8266 |
| 1 | Raspberry Pi | Broker, database, layanan Python |
| TODO | Sensor suhu/kelembapan | TODO: DHT22 / BME280 / lainnya |
| TODO | Catu daya | TODO: tegangan, arus |
| TODO | Kabel jumper, breadboard | |

## Wiring — node sensor ESP32

| Pin sensor | Pin ESP32 | GPIO | Catatan |
|---|---|---|---|
| VCC | 3V3 | — | TODO: cek tegangan sensor (3.3 V atau 5 V) |
| GND | GND | — | |
| DATA | TODO | TODO | TODO: perlu pull-up resistor bila diperlukan |

## Wiring — gateway Wemos

| Fungsi | Pin Wemos | GPIO | Catatan |
|---|---|---|---|
| TODO | TODO | TODO | TODO |

> Jaga tabel ini tetap sinkron dengan `#define` pin di `firmware/*/src/main.cpp`. Ketidakcocokan di sini adalah penyebab paling umum dari bug "kemarin masih jalan".

## Daya

| Board | Sumber | Arus tipikal | Catatan |
|---|---|---|---|
| ESP32 | TODO | TODO | Burst WiFi bisa menarik arus tinggi |
| Wemos D1 mini | TODO | TODO | |
| Raspberry Pi | TODO | TODO | Pakai PSU yang layak; undervoltage menyebabkan reboot acak |

## Jaringan

| Item | Nilai |
|---|---|
| Band WiFi | Hanya 2.4 GHz (ESP32/ESP8266 tidak mendukung 5 GHz) |
| Host broker | IP LAN Raspberry Pi — TODO |
| Port broker | `1883` (tanpa TLS) / `8883` (TLS) |
| DHCP reservation | Disarankan, agar IP broker stabil |

## Foto dan diagram

Simpan gambar di [`images/`](images/) lalu rujuk di sini:

```markdown
![Wiring](images/esp32-wiring.jpg)
```

TODO: tambahkan foto wiring dan foto board dengan label.