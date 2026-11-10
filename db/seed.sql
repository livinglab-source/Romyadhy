-- Optional sample data so a fresh install is not empty.
-- Run AFTER schema.sql:  mysql -u root -p livinglab < db/seed.sql

INSERT INTO devices (device_id, name, board_type, role, location)
VALUES
  ('esp32-01', 'ESP32 sensor node 1', 'esp32',         'sensor-node', 'Lab room A'),
  ('wemos-01', 'Wemos gateway 1',     'wemos-d1-mini', 'gateway',     'Lab room A')
ON DUPLICATE KEY UPDATE name = VALUES(name);