/*
 *  HARDWARE:
 *    Wemos D1 Mini + ADS1115 (I2C addr 0x48)
 *
 *  WIRING:
 *    ADS1115 → Wemos D1 Mini
 *      VDD   → 3.3V
 *      GND   → GND
 *      SCL   → D1 (GPIO 5)
 *      SDA   → D2 (GPIO 4)
 *      ADDR  → GND  (sets I2C address = 0x48)
 *
 *    Level Sensor 3 → ADS1115
 *      VCC → D5 (GPIO 14) — power-gated
 *      OUT → A0 (ADS1115 channel 0)
 *      GND → GND
 *
 *    Level Sensor 4 → ADS1115
 *      VCC → D6 (GPIO 12) — power-gated
 *      OUT → A1 (ADS1115 channel 1)
 *      GND → GND
 *
 *  NOTE: Wemos B is identical hardware to Wemos A. Differences:
 *    - mqtt_client_id = "WEMOS_B"
 *    - mqtt_topic publishes to wemosB (levels 3 & 4)
 *    - JSON keys are "level3" / "level3_cm" and "level4" / "level4_cm"
 *    - Calibration values (calS3, calS4) tuned independently
 *
 *  ═══════════════════════════════════════════════════════════
 *  CALIBRATION WORKFLOW — follow this order:
 *
 *  STEP 1 — DRY calibration
 *    Set  CAL_MODE_DRY true, CAL_MODE_WET false
 *    Keep BOTH sensors completely dry
 *    Reflash → open Serial Monitor 115200 baud
 *    Copy the printed "USE AS adc_min" values into calS3/calS4
 *    Set  CAL_MODE_DRY back to false
 *
 *  STEP 2 — WET calibration
 *    Set  CAL_MODE_WET true, CAL_MODE_DRY false
 *    Submerge BOTH sensors to maximum expected depth
 *    Use your actual nutrient solution, not plain water
 *    Reflash → open Serial Monitor 115200 baud
 *    Copy the printed "USE AS adc_max" values into calS3/calS4
 *    Set  CAL_MODE_WET back to false
 *
 *  STEP 3 — Normal operation
 *    Both CAL_MODE_DRY and CAL_MODE_WET = false
 *    Reflash → device runs normally
 *  ═══════════════════════════════════════════════════════════
 *
 *  MQTT PUBLISH:
 *    Topic : smartgreengarden/waterlevel/wemosB
 *    JSON  : {"level3":<pct>,"level3_cm":<cm>,"level4":<pct>,"level4_cm":<cm>}
 *    Rate  : every PUBLISH_INTERVAL_MS (default 30s)
 *    Retain: true
 *
 *  LWT: {"offline":true} published by broker if node dies
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

// ─── WiFi credentials ────────────────────────────────────────────────────────
const char* ssid     = "LivingLab";
const char* password = "LABTengah2026!";

// ─── MQTT ─────────────────────────────────────────────────────────────────────
const char* mqtt_server    = "192.168.88.88";
const int   mqtt_port      = 1883;
const char* mqtt_client_id = "WEMOS_B";
const char* mqtt_topic     = "smartgreengarden/waterlevel/wemosB";
const char* mqtt_lwt_msg   = "{\"offline\":true}";

// ─── Pin definitions ──────────────────────────────────────────────────────────
#define PIN_SENSOR3_POWER D5
#define PIN_SENSOR4_POWER D6
#define ADS_CHANNEL_S3    0
#define ADS_CHANNEL_S4    1

// ─── Calibration mode flags ───────────────────────────────────────────────────
//  Only ONE should be true at a time. Both false = normal operation.
//
//  CAL_MODE_DRY : sensors must be DRY   → measures adc_min
//  CAL_MODE_WET : sensors must be WET   → measures adc_max
//
#define CAL_MODE_DRY   false   // ← set true for dry calibration
#define CAL_MODE_WET   false   // ← set true for wet calibration
#define CAL_READINGS    20     // readings averaged per sensor per cal session

// ─── Calibration values ───────────────────────────────────────────────────────
//  adc_min      : raw ADC when sensor is completely dry
//  adc_max      : raw ADC when sensor is fully submerged
//  sensor_len_mm: physical sensing strip length in mm (measure your sensor)
//
//  UPDATE THESE after each calibration run using the printed suggestions.
struct LevelCalibration {
  int16_t adc_min;
  int16_t adc_max;
  float   sensor_len_mm;
};

LevelCalibration calS3 = {  2250,  6450, 40.0f };  // Sensor 3 (Ch0) — update after cal
LevelCalibration calS4 = {  1007,  5500, 40.0f };  // Sensor 4 (Ch1) — update after cal

// ─── Sampling settings ────────────────────────────────────────────────────────
#define SAMPLE_COUNT         50    // readings averaged per normal measurement
#define SAMPLE_DELAY_MS      10    // ms between normal samples
#define SENSOR_WARMUP_MS    150    // ms to stabilise after power-on
#define PUBLISH_INTERVAL_MS 30000  // MQTT publish interval (30s)

// ─── Reading result ───────────────────────────────────────────────────────────
struct LevelReading {
  int   pct;   // 0–100%
  float mm;    // 0.0–sensor_len_mm
  float cm;    // 0.0–sensor_len_mm/10
};

// ─── State ────────────────────────────────────────────────────────────────────
Adafruit_ADS1115 ads;
WiFiClient       espClient;
PubSubClient     client(espClient);

LevelReading reading3 = { 0, 0.0f, 0.0f };
LevelReading reading4 = { 0, 0.0f, 0.0f };

unsigned long lastPublish       = 0;
unsigned long lastMqttReconnect = 0;
unsigned long lastWifiReconnect = 0;

const unsigned long mqttReconnectInterval = 5000;
const unsigned long wifiReconnectInterval = 10000;

// ─── captureCalAvg() ──────────────────────────────────────────────────────────
//  Core calibration function used by both DRY and WET modes.
//
//  Powers the sensor → waits 500ms → takes CAL_READINGS samples
//  200ms apart → powers off → prints all individual readings plus
//  statistics (avg / min / max / spread / stability diagnosis).
//
//  For DRY mode : suggested value = avg + 30  (buffer above noise floor)
//  For WET mode : suggested value = avg - 20  (conservative ceiling,
//                 avoids over-reporting 100% due to surface splashing)
//
//  The spread diagnosis tells you if your wiring/sensor is healthy:
//    < 50   = stable    → good, trust the result
//    50–150 = moderate  → acceptable, minor noise
//    > 150  = high      → check GND connection and sensor traces
//
void captureCalAvg(uint8_t adsChannel, uint8_t powerPin,
                   const char* label, bool isDry) {
  const char* modeStr = isDry ? "DRY (adc_min)" : "WET (adc_max)";
  Serial.printf("\n[CAL %s] Sensor %s — taking %d readings...\n",
                isDry ? "DRY" : "WET", label, CAL_READINGS);

  digitalWrite(powerPin, HIGH);
  delay(500); // extended warmup during calibration

  long    total  = 0;
  int16_t minVal =  32767;
  int16_t maxVal = -32768;

  for (int i = 0; i < CAL_READINGS; i++) {
    int16_t r = ads.readADC_SingleEnded(adsChannel);
    total += r;
    if (r < minVal) minVal = r;
    if (r > maxVal) maxVal = r;
    Serial.printf("  [%2d/%2d] raw=%d\n", i + 1, CAL_READINGS, r);
    delay(200); // 200ms apart → genuinely independent samples
  }

  digitalWrite(powerPin, LOW);

  int16_t avg    = (int16_t)(total / CAL_READINGS);
  int16_t spread = maxVal - minVal;

  const char* stability =
    spread < 50  ? "STABLE   - result is reliable" :
    spread < 150 ? "MODERATE - minor noise, acceptable" :
                   "HIGH NOISE - check GND and sensor traces";

  Serial.println("  ------------------------------------------------");
  Serial.printf("  avg    = %d\n",  avg);
  Serial.printf("  min    = %d\n",  minVal);
  Serial.printf("  max    = %d\n",  maxVal);
  Serial.printf("  spread = %d  (%s)\n", spread, stability);
  Serial.println("  ------------------------------------------------");

  if (isDry) {
    // +30 buffer: absorbs ambient humidity and minor surface moisture
    // without pushing the deadband threshold too high
    int16_t suggested = avg + 30;
    Serial.printf("  --> Copy into adc_min for %s: %d\n", label, suggested);
    Serial.printf("      (avg %d + 30 humidity buffer)\n", avg);
  } else {
    // -20 buffer: prevents surface ripple from pinning reading at 100%
    // when the true water surface is just below full
    int16_t suggested = avg - 20;
    Serial.printf("  --> Copy into adc_max for %s: %d\n", label, suggested);
    Serial.printf("      (avg %d - 20 ripple buffer)\n", avg);
  }
  Serial.println("  ------------------------------------------------\n");
}

// ─── readLevel() ──────────────────────────────────────────────────────────────
LevelReading readLevel(uint8_t adsChannel, uint8_t powerPin,
                       const LevelCalibration& cal) {
  digitalWrite(powerPin, HIGH);
  delay(SENSOR_WARMUP_MS);

  long total = 0;
  for (int i = 0; i < SAMPLE_COUNT; i++) {
    total += ads.readADC_SingleEnded(adsChannel);
    delay(SAMPLE_DELAY_MS);
  }
  int16_t avgRaw = (int16_t)(total / SAMPLE_COUNT);
  digitalWrite(powerPin, LOW);

  float   voltage  = ads.computeVolts(avgRaw);
  int16_t range    = cal.adc_max - cal.adc_min;
  int16_t deadband = range / 10;

  if (avgRaw < cal.adc_min + deadband) {
    Serial.printf("  Ch%d raw=%-6d  V=%.3fV  pct=0%%  mm=0.0  cm=0.00  (deadband)\n",
                  adsChannel, avgRaw, voltage);
    return { 0, 0.0f, 0.0f };
  }

  int pct = constrain(
    (int)map(avgRaw, cal.adc_min, cal.adc_max, 0, 100),
    0, 100
  );

  float mm = constrain(
    (avgRaw - cal.adc_min) * cal.sensor_len_mm / (float)range,
    0.0f, cal.sensor_len_mm
  );
  float cm = mm / 10.0f;

  Serial.printf("  Ch%d raw=%-6d  V=%.3fV  pct=%d%%  mm=%.1f  cm=%.2f\n",
                adsChannel, avgRaw, voltage, pct, mm, cm);

  return { pct, mm, cm };
}

// ─── WiFi ─────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("\nConnecting to %s", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n WiFi OK  IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n WiFi timeout - will retry in loop.");
  }
}

void checkAndReconnectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  unsigned long now = millis();
  if (now - lastWifiReconnect < wifiReconnectInterval) return;
  lastWifiReconnect = now;
  Serial.println("WiFi lost - reconnecting...");
  WiFi.reconnect();
}

// ─── MQTT reconnect ───────────────────────────────────────────────────────────
bool reconnectMQTT() {
  if (client.connected()) return true;
  if (WiFi.status() != WL_CONNECTED) return false;
  unsigned long now = millis();
  if (now - lastMqttReconnect < mqttReconnectInterval) return false;
  lastMqttReconnect = now;

  Serial.print("Connecting MQTT...");
  if (client.connect(mqtt_client_id,
                     nullptr, nullptr,
                     mqtt_topic, 0, true,
                     mqtt_lwt_msg)) {
    Serial.println(" OK");
    client.publish(mqtt_topic, "{\"status\":\"online\",\"node\":\"B\"}", true);
    return true;
  }
  Serial.printf(" FAILED state=%d\n", client.state());
  return false;
}

// ─── publishLevels() ──────────────────────────────────────────────────────────
void publishLevels() {
  if (!client.connected()) return;

  char payload[128];
  snprintf(payload, sizeof(payload),
    "{\"level3\":%d,\"level3_cm\":%.2f,\"level4\":%d,\"level4_cm\":%.2f}",
    reading3.pct, reading3.cm,
    reading4.pct, reading4.cm
  );

  client.publish(mqtt_topic, payload, true);
  Serial.printf("[WemosB] %s\n", payload);
}

// ─── runCalibrationMode() ─────────────────────────────────────────────────────
//  Called from setup() when either CAL_MODE_DRY or CAL_MODE_WET is true.
//  Prints a clear header, runs captureCalAvg() for both sensors,
//  prints next-step instructions, then halts — never enters loop().
void runCalibrationMode(bool isDry) {
  Serial.println("\n================================================");
  if (isDry) {
    Serial.println("  CAL MODE: DRY  (measuring adc_min)");
    Serial.println("  Both sensors must be COMPLETELY DRY");
  } else {
    Serial.println("  CAL MODE: WET  (measuring adc_max)");
    Serial.println("  Both sensors must be FULLY SUBMERGED");
    Serial.println("  Use your actual nutrient solution");
  }
  Serial.println("  Starting in 3 seconds...");
  Serial.println("================================================");
  delay(3000);

  captureCalAvg(ADS_CHANNEL_S3, PIN_SENSOR3_POWER, "S3-Ch0", isDry);
  delay(1000);
  captureCalAvg(ADS_CHANNEL_S4, PIN_SENSOR4_POWER, "S4-Ch1", isDry);

  Serial.println("================================================");
  Serial.println("  CALIBRATION COMPLETE");
  if (isDry) {
    Serial.println("  1. Copy the adc_min values printed above");
    Serial.println("     into calS3.adc_min and calS4.adc_min");
    Serial.println("  2. Set CAL_MODE_DRY = false");
    Serial.println("  3. Next: run CAL_MODE_WET with sensors submerged");
  } else {
    Serial.println("  1. Copy the adc_max values printed above");
    Serial.println("     into calS3.adc_max and calS4.adc_max");
    Serial.println("  2. Set CAL_MODE_WET = false");
    Serial.println("  3. Both modes false = normal operation");
  }
  Serial.println("================================================\n");

  while (true) delay(1000); // halt — do not proceed to loop()
}

// ─── setup() ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== SmartGreenGarden - Wemos B (Level 3 & 4) ===");

  pinMode(PIN_SENSOR3_POWER, OUTPUT); digitalWrite(PIN_SENSOR3_POWER, LOW);
  pinMode(PIN_SENSOR4_POWER, OUTPUT); digitalWrite(PIN_SENSOR4_POWER, LOW);

  Wire.begin();
  if (!ads.begin(0x48)) {
    Serial.println("ADS1115 not found! Check wiring (SDA=D2, SCL=D1, ADDR=GND).");
    pinMode(LED_BUILTIN, OUTPUT);
    while (true) {
      digitalWrite(LED_BUILTIN, LOW);  delay(200);
      digitalWrite(LED_BUILTIN, HIGH); delay(200);
    }
  }
  ads.setGain(GAIN_ONE);
  Serial.println("ADS1115 OK");

  // ── Calibration mode check — runs before WiFi, halts after ───────
  if (CAL_MODE_DRY && CAL_MODE_WET) {
    Serial.println("ERROR: CAL_MODE_DRY and CAL_MODE_WET cannot both be true.");
    Serial.println("Set only ONE to true at a time. Halting.");
    while (true) delay(1000);
  }
  if (CAL_MODE_DRY) { runCalibrationMode(true);  } // never returns
  if (CAL_MODE_WET) { runCalibrationMode(false); } // never returns
  // ─────────────────────────────────────────────────────────────────

  // Normal operation — print active calibration for verification
  Serial.printf("Calibration S3: min=%-6d  max=%-6d  len=%.0fmm\n",
                calS3.adc_min, calS3.adc_max, calS3.sensor_len_mm);
  Serial.printf("Calibration S4: min=%-6d  max=%-6d  len=%.0fmm\n",
                calS4.adc_min, calS4.adc_max, calS4.sensor_len_mm);

  connectWiFi();
  client.setServer(mqtt_server, mqtt_port);
  client.setBufferSize(512); // prevents silent publish failures on larger payloads
  delay(3000);
}

// ─── loop() ───────────────────────────────────────────────────────────────────
void loop() {
  checkAndReconnectWiFi();
  reconnectMQTT();
  client.loop();

  unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;

    Serial.println("--- Reading Level Sensors ---");
    reading3 = readLevel(ADS_CHANNEL_S3, PIN_SENSOR3_POWER, calS3);
    reading4 = readLevel(ADS_CHANNEL_S4, PIN_SENSOR4_POWER, calS4);

    Serial.printf("  Level3: %d%%  %.1fmm  %.2fcm\n",
                  reading3.pct, reading3.mm, reading3.cm);
    Serial.printf("  Level4: %d%%  %.1fmm  %.2fcm\n",
                  reading4.pct, reading4.mm, reading4.cm);

    publishLevels();
  }
}
