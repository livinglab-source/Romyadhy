-- Living Lab database schema (MariaDB 10.6+ / MySQL 8+)
-- Source of truth: this file. docs/database.md explains it.
-- Apply with:  mysql -u root -p < db/schema.sql
--
-- These are the tables the running code actually uses:
--   hydroponic_water_data_romy  -> written by services/data-logger/dataSave.py
--   relay_logs                  -> written by services/telegram-bot/telegrambot.py

CREATE DATABASE IF NOT EXISTS livinglab
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE livinglab;

-- ---------------------------------------------------------------------------
-- Sensor history. dataSave.py creates this table itself if missing, but it is
-- defined here so a fresh install and the docs agree.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hydroponic_water_data_romy (
  id                      INT(11) AUTO_INCREMENT PRIMARY KEY,
  datetime                DATETIME NOT NULL,
  tds1_ppm                DECIMAL(10,2),
  tds2_ppm                DECIMAL(10,2),
  delta_tds               DECIMAL(5,2),
  turbidity               DECIMAL(10,2),
  flow_rate               DECIMAL(10,2),
  water_level_1_percent   DECIMAL(5,2),
  water_level_1_status    VARCHAR(10),
  water_level_2_percent   DECIMAL(5,2),
  water_level_2_status    VARCHAR(10),
  water_level_3_percent   DECIMAL(5,2),
  water_level_3_status    VARCHAR(10),
  water_level_4_percent   DECIMAL(5,2),
  water_level_4_status    VARCHAR(10),
  -- Integer code 0-4 (-1 = unknown). The human-readable label lives in the
  -- application, not the column.
  water_quality           INT,
  uploaded_to_cloud       TINYINT(1) DEFAULT 0,
  KEY idx_sensor_datetime (datetime)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Relay event log: one row per ON/OFF transition, written by the Telegram bot.
-- The OFF row carries the duration measured since the matching ON.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS relay_logs (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  relay_name       VARCHAR(64) NOT NULL,          -- irigasi | kuras_tandon | ...
  state            ENUM('ON','OFF') NOT NULL,
  event_time       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  duration_seconds INT UNSIGNED NULL,             -- filled on the OFF row
  mode             VARCHAR(16) NULL,              -- auto | manual at the time
  PRIMARY KEY (id),
  KEY idx_relay_logs_name_time (relay_name, event_time),
  KEY idx_relay_logs_time (event_time)
) ENGINE=InnoDB;