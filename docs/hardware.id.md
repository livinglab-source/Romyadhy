# Perangkat Keras

[English](hardware.md) | [Bahasa Indonesia](hardware.id.md)

> Nama folder menunjukkan **peran**. Tabel ini memetakan peran ke board yang dipakai.

## Pemetaan board → peran

| Peran | Board | Folder | Device id (MQTT) |
|---|---|---|---|
| Node sensor | ESP32 DevKit (WROOM-32) | `firmware/esp32-sensor-node` | `ESP32_SENSOR` |
| Gateway / relay | Wemos D1 mini (ESP8266) | `firmware/wemos-gateway` | `wemos-01` |
| Broker + layanan | Raspberry Pi | `services/`, `deploy/` | — |

## Daftar komponen (BOM)

| Jumlah | Item | Catatan |
|---|---|---|
| 1 | ESP32 DevKit (WROOM-32) | Node sensor utama |
| 1 | ADS1115 ADC 16-bit | I²C, alamat 0x48, untuk TDS + kekeruhan |
| 2 | Probe TDS Gravity | DFRobot atau kompatibel |
| 1 | Sensor kekeruhan (analog) | Output 0–5 V, dibaca via ADS1115 AIN0 |
| 1 | Sensor aliran YF-S201 (atau setara) | Output pulsa, 7,5 pulsa per liter |
| 4 | Sensor level air resistif | Output analog |
| 1 | LCD 16×2 I²C | Alamat 0x27 |
| 1 | Wemos D1 mini | Gateway relay (ESP8266) |
| 1 | Raspberry Pi | Broker MQTT, database, layanan Python |
| 1 | Power supply 5 V | ≥ 2 A disarankan (lonjakan arus WiFi) |

## Wiring — node sensor ESP32

### ADS1115 (I²C)

| Pin ADS1115 | Pin ESP32 | Catatan |
|---|---|---|
| VDD | 3V3 | — |
| GND | GND | — |
| SCL | GPIO 22 | I²C clock standar ESP32 |
| SDA | GPIO 21 | I²C data standar ESP32 |
| ADDR | GND | Mengatur alamat I²C ke 0x48 |
| AIN0 | Output sensor kekeruhan | Pakai voltage divider jika tegangan sensor > 3,3 V |
| AIN2 | Output probe TDS 1 | — |
| AIN3 | Output probe TDS 2 | — |

### Sensor level air

| Sinyal | GPIO ESP32 | Catatan |
|---|---|---|
| Analog level 1 | GPIO 32 | ADC1_CH4 |
| Analog level 2 | GPIO 33 | ADC1_CH5 |
| Analog level 3 | GPIO 34 | ADC1_CH6, input-only |
| Analog level 4 | GPIO 35 | ADC1_CH7, input-only |
| VCC (keempatnya) | GPIO 26 | Dinyalakan HIGH hanya saat pembacaan untuk mengurangi korosi |

### Sensor aliran

| Sinyal | GPIO ESP32 | Catatan |
|---|---|---|
| Sinyal (kuning) | GPIO 27 | `INPUT_PULLUP`, interrupt pada RISING |
| VCC (merah) | 5 V | — |
| GND (hitam) | GND | — |

### LCD (I²C, berbagi bus dengan ADS1115)

| Pin LCD | Pin ESP32 |
|---|---|
| VCC | 5 V |
| GND | GND |
| SCL | GPIO 22 |
| SDA | GPIO 21 |

> Jaga tabel ini tetap sinkron dengan assignment pin `#define` / `const` di `firmware/esp32-sensor-node/keren-12.ino`.

## Wiring — Wemos A & B (Node Level Air)

Kedua node identik secara hardware. Flash sketch yang sesuai (`wemos_a_*` atau `wemos_b_*`) untuk mengatur identitas MQTT.

### ADS1115 (I²C — dipakai kedua Wemos)

| Pin ADS1115 | Pin Wemos | GPIO | Catatan |
|---|---|---|---|
| VDD | 3V3 | — | — |
| GND | GND | — | — |
| SCL | D1 | GPIO 5 | — |
| SDA | D2 | GPIO 4 | — |
| ADDR | GND | — | Mengatur alamat I²C ke 0x48 |
| AIN0 | — | — | Sensor 1 (Wemos A) / Sensor 3 (Wemos B) |
| AIN1 | — | — | Sensor 2 (Wemos A) / Sensor 4 (Wemos B) |

### Power gating sensor level

| Sinyal | Pin Wemos | GPIO | Sensor |
|---|---|---|---|
| VCC sensor pertama | D5 | GPIO 14 | S1 pada A / S3 pada B |
| VCC sensor kedua | D6 | GPIO 12 | S2 pada A / S4 pada B |

> GND sensor → GND Wemos. OUT sensor → ADS1115 AINx (lihat tabel di atas).

## Daya

| Board | Sumber | Catatan |
|---|---|---|
| ESP32 | 5 V via USB atau VIN | Burst WiFi bisa menarik arus tinggi; pakai supply ≥ 2 A |
| Wemos D1 mini | 5 V via USB atau pin 5 V | — |
| Raspberry Pi | 5 V / 3 A (PSU resmi) | Undervoltage menyebabkan reboot acak |

## Jaringan

| Item | Nilai |
|---|---|
| SSID WiFi | `SGG X FSR` (2,4 GHz) |
| Band WiFi | Hanya 2,4 GHz (ESP32/ESP8266 tidak mendukung 5 GHz) |
| Host broker | `192.168.88.88` (Raspberry Pi, statis/reserved) |
| Port broker | `1883` (tanpa TLS) |
| DHCP reservation | Wajib — IP broker di-hardcode di firmware |

## Foto dan diagram

Simpan gambar di [`images/`](images/) lalu rujuk di sini:

```markdown
![Wiring](images/esp32-wiring.jpg)
```

TODO: tambahkan foto wiring dan foto board dengan label.
