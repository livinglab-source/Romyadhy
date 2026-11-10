-- Living Lab database schema (MariaDB 10.6+ / MySQL 8+)
-- Source of truth: this file. docs/database.md explains it.
-- Apply with:  mysql -u root -p < db/schema.sql

CREATE DATABASE IF NOT EXISTS livinglab
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE livinglab;

-- ---------------------------------------------------------------------------
-- Devices: one row per physical board
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id     VARCHAR(64)  NOT NULL,          -- MQTT id, e.g. esp32-01
  name          VARCHAR(128) NULL,              -- human friendly name
  board_type    VARCHAR(32)  NOT NULL,          -- esp32 | wemos-d1-mini
  role          VARCHAR(64)  NOT NULL,          -- sensor-node | gateway | ...
  location      VARCHAR(128) NULL,
  firmware      VARCHAR(32)  NULL,
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_devices_device_id (device_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Readings: append-only sensor data
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS readings (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id    VARCHAR(64)  NOT NULL,
  recorded_at  DATETIME(3)  NOT NULL,           -- device timestamp, ms precision
  temp_c       DECIMAL(5,2) NULL,               -- -99.99 .. 999.99
  hum_pct      DECIMAL(5,2) NULL,
  -- TODO: add the columns your nodes actually publish, e.g.
  -- soil_pct  DECIMAL(5,2) NULL,
  -- light_lux DECIMAL(8,2) NULL,
  -- relay     TINYINT(1)   NULL,
  seq          INT UNSIGNED NULL,
  created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_readings_device_time (device_id, recorded_at),
  KEY idx_readings_time (recorded_at),
  CONSTRAINT fk_readings_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Device status: latest known state per device (one row per device)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS device_status (
  device_id   VARCHAR(64) NOT NULL,
  online      TINYINT(1)  NOT NULL DEFAULT 0,
  rssi        SMALLINT    NULL,
  uptime_s    BIGINT UNSIGNED NULL,
  last_seen   DATETIME(3) NOT NULL,
  PRIMARY KEY (device_id),
  CONSTRAINT fk_status_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Alerts: threshold breaches and notifications sent
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id   VARCHAR(64) NOT NULL,
  kind        VARCHAR(32) NOT NULL,     -- temp_high | offline | ...
  message     VARCHAR(512) NOT NULL,
  severity    ENUM('info','warning','critical') NOT NULL DEFAULT 'warning',
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  notified_at DATETIME(3) NULL,          -- NULL = not yet sent to Telegram
  PRIMARY KEY (id),
  KEY idx_alerts_device_time (device_id, created_at),
  KEY idx_alerts_pending (notified_at),
  CONSTRAINT fk_alerts_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;