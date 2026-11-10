# Gateway Wemos

[English](README.md) | [Bahasa Indonesia](README.id.md)

TODO: satu kalimat yang menjelaskan fungsi board ini (kontrol relay? node sensor kedua? gateway MQTT?).

- Peran: TODO
- Board: Wemos D1 mini (ESP8266)
- Device id: `wemos-01`

## Tanggung jawab

- TODO
- Subscribe `livinglab/wemos-01/cmd`
- Publish `livinglab/wemos-01/status` (retained) + Last Will

## Perangkat keras

| Komponen | Model | Catatan |
|---|---|---|
| MCU | Wemos D1 mini | ESP8266, hanya WiFi 2.4 GHz |
| TODO | TODO | TODO |

Wiring: [../../docs/hardware.id.md](../../docs/hardware.id.md#wiring--gateway-wemos)

## Konfigurasi

```bash
cp include/config.h.example include/config.h
```

| Key | Arti |
|---|---|
| `WIFI_SSID` / `WIFI_PASSWORD` | WiFi lab (2.4 GHz) |
| `MQTT_HOST` / `MQTT_PORT` | Broker Raspberry Pi |
| `MQTT_USER` / `MQTT_PASS` | Kredensial Mosquitto |
| `DEVICE_ID` | `wemos-01` |

## MQTT

| Arah | Topik | Payload |
|---|---|---|
| subscribe | `livinglab/wemos-01/cmd` | `{"schema":1,"action":"set_relay","value":1}` |
| publish (retained) | `livinglab/wemos-01/status` | `{"schema":1,"online":true,"fw":"1.0.0"}` |

## Build dan flash

```bash
pio run
pio run -t upload
pio device monitor -b 115200
```

## Troubleshooting

| Gejala | Solusi |
|---|---|
| Tidak bisa konek | Hanya 2.4 GHz; cek kredensial |
| Relay tidak berpindah | Pastikan pin di tabel wiring sama dengan firmware |
| Client id duplikat | `DEVICE_ID` harus unik |

Selengkapnya: [../../docs/troubleshooting.id.md](../../docs/troubleshooting.id.md)