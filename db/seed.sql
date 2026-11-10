-- Optional sample data so a fresh install is not empty.
-- Run AFTER schema.sql:  mysql -u root -p livinglab < db/seed.sql
-- Both tables are append-only logs written by the services, so there is no
-- device registry to seed. Insert a marker row for smoke-testing instead.

INSERT INTO hydroponic_water_data_romy
  (datetime, tds1_ppm, tds2_ppm, delta_tds, turbidity, flow_rate,
   water_level_1_percent, water_level_1_status,
   water_level_2_percent, water_level_2_status,
   water_level_3_percent, water_level_3_status,
   water_level_4_percent, water_level_4_status,
   water_quality, uploaded_to_cloud)
VALUES
  (NOW(), 800.00, 790.00, 10.00, 12.50, 6.20,
   88.00, 'Full', 64.00, 'High', 41.00, 'Medium', 27.00, 'Low', 2, 0);