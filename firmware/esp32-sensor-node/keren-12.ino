#include <WiFi.h>
#include <EEPROM.h>
#include <GravityTDS.h>
#include <Adafruit_ADS1X15.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <time.h>
#include <PubSubClient.h>

// === WiFi ===
const char* ssid = "SGG X FSR";
const char* password = "12345678";

// === MQTT RASPI BROKER ===
const char* mqtt_server = "192.168.88.88";
const int mqtt_port = 1883;
const char* mqtt_client_id = "ESP32_SENSOR";

// === MQTT TOPIC CALLIBRATIONS TDS ===
const char* mqtt_topic_cal_tds1 = "smartgreengarden/sensor/kalibrasi/tds1";
const char* mqtt_topic_cal_tds2 = "smartgreengarden/sensor/kalibrasi/tds2";


WiFiClient espClient;
PubSubClient client(espClient);

// === LCD ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === ADS1115 ===
Adafruit_ADS1115 ads;

// === TDS Sensors ===
GravityTDS tds1, tds2;
float temperature = 25.0;
float tdsValue1 = 0.0;
float tdsValue2 = 0.0;
float voltageTDS1 = 0.0;
float voltageTDS2 = 0.0;

// === Turbidity Sensor ===
float turbidityNTU = 0.0;
float voltageTurb = 0.0;

// === Turbidity Calibration ===
// Variabel kalibrasi A dan B untuk rumus: NTU = (A * Voltage) + B
float turbidityCalibA = 1.0; // Nilai default sementara
float turbidityCalibB = 0.0; // Nilai default sementara
#define EEPROM_ADDR_TURB_CAL 20

// === Flow Sensor ===
const int flowPin = 27;
volatile int flowPulseCount = 0;
float flowRateLMin = 0.0;

// === Level Sensors ===
const int sensorPins[4] = {32, 33, 34, 35};
int percent[4] = {0, 0, 0, 0};
String category[4] = {"Empty", "Empty", "Empty", "Empty"};
int adcLevel[4] = {0, 0, 0, 0};

// [FIX] Definisi struct dipindahkan ke atas, SEBELUM digunakan.
struct SensorLinearCalibration {
  int adc_min; // Nilai ADC saat level terendah (0%)
  int adc_max; // Nilai ADC saat level tertinggi (100%)
};

//linear calibrasion for water level
SensorLinearCalibration linear_calibrations[4] = {
  {300, 687}, // level1
  {200, 422}, // level2
  {100, 949}, // level3
  {300, 717}  //level4
};

// Pin water level VCC
#define LEVEL_SENSORS_POWER_PIN 26

// EEPROM Addresses
#define EEPROM_ADDR_TDS1 0
#define EEPROM_ADDR_TDS2 10

// Timers
unsigned long lastSensorUpdate = 0;
unsigned long lastWaterLevelRead = 0;
unsigned long lastDisplayUpdate = 0;
const unsigned long sensorInterval = 5000;
const unsigned long waterLevelInterval = 60000;
const unsigned long displayInterval = 3000;
int displayState = 0;
String serialInput = "";

// === Function: 2-Point Turbidity Calibration ===
void calibrateTurbidity2Point() {
  Serial.println("\n=== Kalibrasi Turbidity (0–50 NTU) ===");
  Serial.println("1. Siapkan air jernih (0 NTU), tekan ENTER saat siap.");
  while (!Serial.available()) delay(10);
  while (Serial.available()) Serial.read(); // Bersihkan buffer serial

  float v0 = 0;
  Serial.print("Membaca tegangan 0 NTU...");
  for (int i = 0; i < 20; i++) {
    int16_t adc = ads.readADC_SingleEnded(0); // Baca dari AIN0
    v0 += ads.computeVolts(adc);
    delay(100);
    Serial.print(".");
  }
  v0 /= 20.0;
  Serial.println(" Selesai!");
  Serial.print("Tegangan (0 NTU): "); Serial.println(v0, 6);

  Serial.println("\n2. Pindahkan sensor ke larutan 50 NTU, tekan ENTER saat siap.");
  while (!Serial.available()) delay(10);
  while (Serial.available()) Serial.read(); // Bersihkan buffer serial

  float v50 = 0;
  Serial.print("Membaca tegangan 50 NTU...");
  for (int i = 0; i < 20; i++) {
    int16_t adc = ads.readADC_SingleEnded(0); // HARUS AIN0
    v50 += ads.computeVolts(adc);
    delay(100);
    Serial.print(".");
  }
  v50 /= 20.0;
  Serial.println(" Selesai!");
  Serial.print("Tegangan (50 NTU): "); Serial.println(v50, 6);

  // Hitung slope (A) dan intercept (B) (linear 2 titik)
  // Rumus: NTU = A * Voltage + B
  turbidityCalibA = (50.0 - 0.0) / (v50 - v0); // A = (y2 - y1) / (x2 - x1)
  turbidityCalibB = 0.0 - turbidityCalibA * v0; // B = y1 - A * x1

  // Simpan ke EEPROM
  EEPROM.put(EEPROM_ADDR_TURB_CAL, turbidityCalibA);
  EEPROM.put(EEPROM_ADDR_TURB_CAL + sizeof(float), turbidityCalibB);
  EEPROM.commit();

  Serial.println("\n✅ Kalibrasi turbidity selesai!");
  Serial.println("Rumus baru: NTU = (A * Voltage) + B");
  Serial.print("A (Slope)     = "); Serial.println(turbidityCalibA, 6);
  Serial.print("B (Intercept) = "); Serial.println(turbidityCalibB, 6);
  Serial.println("Nilai disimpan ke EEPROM.\n");
}


void IRAM_ATTR flowISR() {
  flowPulseCount++;
}

// BARU: Fungsi konversi ADC ke persentase yang presisi menggunakan pemetaan linear.
// Sekarang compiler sudah tahu apa itu 'SensorLinearCalibration'
int adcToPrecisePercent(int adcValue, const SensorLinearCalibration& cal) {
  // Petakan nilai ADC (dari rentang min-max) ke persentase (rentang 0-100)
  long mapped_percent = map(adcValue, cal.adc_min, cal.adc_max, 0, 100);
  
  // Batasi hasilnya agar selalu di antara 0 dan 100 untuk keamanan
  return constrain(mapped_percent, 0, 100);
}


// Fungsi ini bekerja berdasarkan hasil persentase yang presisi, bukan ADC.
String getLevelCategory(int percentValue) {
  if (percentValue == 0) return "Empty";
  if (percentValue <= 25) return "Low";
  if (percentValue <= 50) return "Med";
  if (percentValue <= 75) return "High";
  return "Full";
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

// === CALLBCAK MQTT TOPICS CALLIBRATIONS ===
void callback(char* topic, byte* payload, unsigned int length){
  char message[length + 1];
  strncpy(message, (char*)payload, length);
  message[length] = '\0';

  Serial.print("🔧 MQTT Command Received on topic [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);

  // Checking CALTDS1
  if (strcmp(topic, mqtt_topic_cal_tds1) == 0) {
    float targetTDS = atof(message); // Konversi string payload ke float
    if (targetTDS > 0) {
      Serial.printf("Memulai kalibrasi TDS1 via MQTT ke target: %.2f ppm\n", targetTDS);
      calibrateTDS1(targetTDS);
    }
  }

  // Checking CALLTDS2
  else if (strcmp(topic, mqtt_topic_cal_tds2) == 0) {
    float targetTDS = atof(message); // Konversi string payload ke float
    if (targetTDS > 0) {
      Serial.printf("Memulai kalibrasi TDS2 via MQTT ke target: %.2f ppm\n", targetTDS);
      calibrateTDS2(targetTDS);
    }
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect(mqtt_client_id)) { 
      client.subscribe(mqtt_topic_cal_tds1); //add tds1
      client.subscribe(mqtt_topic_cal_tds2); //add tds2
      Serial.println("✅ Connected to MQTT!");
    } else {
      Serial.print("❌ Failed. State=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s...");
      delay(5000);
    }
  }
}

void publishSensorData() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  String payload = "{";
  payload += "\"tds1\":" + String(tdsValue1, 2) + ",";
  payload += "\"tds2\":" + String(tdsValue2, 2) + ",";
  payload += "\"turbidity\":" + String(turbidityNTU, 2) + ",";
  payload += "\"voltage_turbidity\":" + String(voltageTurb, 3) + ",";
  payload += "\"FlowRate\":" + String(flowRateLMin, 2) + ",";
  payload += "\"Level1\":" + String(percent[0]) + ",";
  payload += "\"adc_level1\":" + String(adcLevel[0]) + ",";
  payload += "\"Level2\":" + String(percent[1]) + ",";
  payload += "\"adc_level2\":" + String(adcLevel[1]) + ",";
  payload += "\"Level3\":" + String(percent[2]) + ",";
  payload += "\"adc_level3\":" + String(adcLevel[2]) + ",";
  payload += "\"Level4\":" + String(percent[3]) + ",";   
  payload += "\"adc_level4\":" + String(adcLevel[3]);
  payload += "}";

  client.publish("smartgreengarden/sensor/data", payload.c_str());
  Serial.println("📤 [" + String(millis()) + "ms] MQTT Published: " + payload);
}

void setupTDS(GravityTDS& sensor, int eepromAddr, const char* name) { 
  sensor.begin();

  float savedK;
  EEPROM.get(eepromAddr, savedK);
  if (!isnan(savedK) && savedK > 0.1 && savedK < 5.0) {
    sensor.setKvalue(savedK);
    Serial.print("✅ Loaded K untuk ");
    Serial.print(name);
    Serial.print(": ");
    Serial.println(savedK, 4);
  } else {
    Serial.print("⚠️ Tidak ada nilai K valid untuk ");
    Serial.println(name);
    savedK = 1.0; // Nilai K default
    sensor.setKvalue(savedK);
    EEPROM.put(eepromAddr, savedK);
    EEPROM.commit();
    Serial.print("✅ Nilai K default (1.0) diset untuk ");
    Serial.println(name);
  }
}
void calibrateTDS1(float targetTDS) { 
  int16_t raw1 = ads.readADC_SingleEnded(2);
  float voltage1 = ads.computeVolts(raw1);        
  tds1.setTemperature(temperature);
  tds1.updateByVoltage(voltage1);
  tdsValue1 = tds1.getTdsValue();

  if (tdsValue1 > 0 && targetTDS > 0) {
    float newK1 = tds1.getKvalue() * (targetTDS / tdsValue1);
    tds1.setKvalue(newK1);
    EEPROM.put(EEPROM_ADDR_TDS1, newK1);
    EEPROM.commit();
    Serial.println("✅ Kalibrasi selesai untuk TDS1.");
    Serial.print("TDS1 K baru: "); Serial.println(newK1, 4);
    Serial.printf("TDS1: %.2f ppm, Voltage: %.3f V\n", tdsValue1, voltage1);
    Serial.printf("Target TDS1: %.2f ppm\n", targetTDS);
  } else {
    Serial.println("❌ Kalibrasi gagal untuk TDS1. TDS atau target tidak valid.");
    Serial.printf("TDS1: %.2f ppm, Voltage: %.3f V\n", tdsValue1, voltage1);
    Serial.printf("Target TDS1: %.2f ppm\n", targetTDS);
  }
}
void calibrateTDS2(float targetTDS) { 
  int16_t raw2 = ads.readADC_SingleEnded(3);
  float voltage2 = ads.computeVolts(raw2); 
  tds2.setTemperature(temperature);
  tds2.updateByVoltage(voltage2);
  tdsValue2 = tds2.getTdsValue();

  if (tdsValue2 > 0 && targetTDS > 0) {
    float newK2 = tds2.getKvalue() * (targetTDS / tdsValue2);
    tds2.setKvalue(newK2);
    EEPROM.put(EEPROM_ADDR_TDS2, newK2);
    EEPROM.commit();
    Serial.println("✅ Kalibrasi selesai untuk TDS2.");
    Serial.print("TDS2 K baru: "); Serial.println(newK2, 4);
    Serial.printf("TDS2: %.2f ppm, Voltage: %.3f V\n", tdsValue2, voltage2);
    Serial.printf("Target TDS2: %.2f ppm\n", targetTDS);
  } else {
    Serial.println("❌ Kalibrasi gagal untuk TDS2. TDS atau target tidak valid.");
    Serial.printf("TDS2: %.2f ppm, Voltage: %.3f V\n", tdsValue2, voltage2);
    Serial.printf("Target TDS2: %.2f ppm\n", targetTDS);
  }
}

void handleSerialInput() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialInput.length() > 0) { // Hanya proses jika ada perintah
        if (serialInput.startsWith("CALTDS1 ")) {
          float target = serialInput.substring(8).toFloat();
          Serial.print("🔧 Kalibrasi TDS1 dimulai ke nilai: ");
          Serial.println(target);
          calibrateTDS1(target);
        } else if (serialInput.startsWith("CALTDS2 ")) {
          float target = serialInput.substring(8).toFloat();
          Serial.print("🔧 Kalibrasi TDS2 dimulai ke nilai: ");
          Serial.println(target);
          calibrateTDS2(target);
        } else if (serialInput == "CALTURB") {
          calibrateTurbidity2Point();
        } else if (serialInput == "exit") {
          Serial.println("👋 Keluar dari mode kalibrasi. (Fitur ini belum diimplementasikan)");
        } else {
          Serial.println("❓ Perintah tidak dikenali. Gunakan:");
          Serial.println("   'CALTDS1 <nilai>', 'CALTDS2 <nilai>'");
          Serial.println("   'CALTURB', atau 'exit'");
        }
      }
      serialInput = ""; // Bersihkan string input setelah diproses
    } else if (isprint(c)) { // Hanya tambahkan karakter yang bisa dicetak
      serialInput += c;
    }
  }
}

void loadTurbidityCalibration() { 
  float a, b;
  EEPROM.get(EEPROM_ADDR_TURB_CAL, a);
  EEPROM.get(EEPROM_ADDR_TURB_CAL + sizeof(float), b);
  
  if (!isnan(a) && !isnan(b) && a != 0.0) {
    turbidityCalibA = a;
    turbidityCalibB = b;
    Serial.println("✅ Kalibrasi Turbidity (A*V + B) dimuat dari EEPROM");
    Serial.print("A = "); Serial.println(turbidityCalibA, 6);
    Serial.print("B = "); Serial.println(turbidityCalibB, 2);
  } else {
    Serial.println("⚠️ Kalibrasi turbiditas tidak valid atau belum di-set.");
    Serial.println("⚠️ Gunakan nilai default (A=1, B=0). HARAP SEGERA KALIBRASI!");
    Serial.println("⚠️ Kirim 'CALTURB' via Serial Monitor untuk memulai.");
    turbidityCalibA = 1.0; 
    turbidityCalibB = 0.0;
  }
}

void checkSensors() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Checking Sensors");
  lcd.setCursor(0, 1);
  lcd.print("Please wait...");
  delay(2000);

  bool tds1Ready = false, tds2Ready = false, turbidityReady = false, flowReady = false;
  bool levelReady[4] = {false, false, false, false};

  int16_t raw1 = ads.readADC_SingleEnded(2);
  float voltage1 = ads.computeVolts(raw1); 
  tds1.setTemperature(temperature);
  tds1.updateByVoltage(voltage1);
  tdsValue1 = tds1.getTdsValue();
  tds1Ready = (tdsValue1 >= 0 && !isnan(tdsValue1) && voltage1 > 0);
  int16_t raw2 = ads.readADC_SingleEnded(3);
  float voltage2 = ads.computeVolts(raw2); 
  tds2.setTemperature(temperature);
  tds2.updateByVoltage(voltage2);
  tdsValue2 = tds2.getTdsValue();
  tds2Ready = (tdsValue2 >= 0 && !isnan(tdsValue2) && voltage2 > 0);

  Serial.printf("RAW1=%d | V1=%.3f V | TDS1=%.2f ppm | K1=%.4f\n",
                raw1, voltage1, tdsValue1, tds1.getKvalue());
  Serial.printf("RAW2=%d | V2=%.3f V | TDS2=%.2f ppm | K2=%.4f\n",
                raw2, voltage2, tdsValue2, tds2.getKvalue());

  int adcTurb = ads.readADC_SingleEnded(0);
  voltageTurb = ads.computeVolts(adcTurb); 
  
  // Perhitungan NTU berbasis VOLTAGE
  turbidityNTU = (turbidityCalibA * voltageTurb) + turbidityCalibB; 
  if (turbidityNTU < 0) turbidityNTU = 0; 

  turbidityReady = (voltageTurb >= 0 && !isnan(voltageTurb) && !isnan(turbidityNTU));
  
  flowPulseCount = 0;
  delay(1000);
  flowReady = (digitalRead(flowPin) != -1);

  digitalWrite(LEVEL_SENSORS_POWER_PIN, HIGH);
  delay(200);
  for (int i = 0; i < 4; i++) {
    int adc = analogRead(sensorPins[i]);
    levelReady[i] = (adc >= 0 && adc <= 4095);
    percent[i] = adcToPrecisePercent(adc, linear_calibrations[i]); 
    category[i] = getLevelCategory(percent[i]);                   
  }
  digitalWrite(LEVEL_SENSORS_POWER_PIN, LOW);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("TDS1: "); lcd.print(tds1Ready ? "Ready" : "Fail");
  lcd.setCursor(0, 1);
  lcd.print("TDS2: "); lcd.print(tds2Ready ? "Ready" : "Fail");
  delay(2000);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Turbidity: "); lcd.print(turbidityReady ? "Ready" : "Fail");
  lcd.setCursor(0, 1);
  lcd.print("Flow: "); lcd.print(flowReady ? "Ready" : "Fail");
  delay(2000);
  for (int i = 0; i < 4; i++) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Level "); lcd.print(i + 1); lcd.print(": "); lcd.print(levelReady[i] ? "Ready" : "Fail");
    delay(2000);
  }
  Serial.println("======= Sensor Readiness Check =======");
  Serial.printf("TDS1: %s\n", tds1Ready ? "Ready ✅" : "Fail ❌");
  Serial.printf("TDS2: %s\n", tds2Ready ? "Ready ✅" : "Fail ❌");
  Serial.printf("Turbidity: %s\n", turbidityReady ? "Ready ✅" : "Fail ❌");
  Serial.printf("Flow Sensor: %s\n", flowReady ? "Ready ✅" : "Fail ❌");
  for (int i = 0; i < 4; i++) {
    Serial.printf("Water Level %d: %s\n", i + 1, levelReady[i] ? "Ready ✅" : "Fail ❌");
  }
  Serial.println("=====================================\n");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("All Sensors");
  lcd.setCursor(0, 1);
  lcd.print("Checked!");
  delay(1500);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  lcd.init(); lcd.backlight();
  lcd.print("Connecting WiFi");
  connectWiFi();
  configTime(8 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  lcd.clear(); lcd.print("WiFi Connected!"); delay(1500);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback); 
  EEPROM.begin(512);
  pinMode(LEVEL_SENSORS_POWER_PIN, OUTPUT);
  digitalWrite(LEVEL_SENSORS_POWER_PIN, LOW);
  
  if (!ads.begin()) {
    Serial.println("❌ Gagal mendeteksi ADS1115");
    lcd.clear(); lcd.print("ADS1115 Error!");
    while (1);
  } else {
    Serial.println("✅ ADS1115 terdeteksi");
  }

  ads.setGain(GAIN_ONE);
  Serial.print("ADS1115 gain set: ");
  Serial.println("GAIN_ONE (±4.096V)");

  setupTDS(tds1, EEPROM_ADDR_TDS1, "TDS1");
  setupTDS(tds2, EEPROM_ADDR_TDS2, "TDS2");
  
  // Note: tds1.setPin(2) tidak diperlukan karena Anda menggunakan updateByVoltage()
  // tds1.setPin(2); 
  // tds2.setPin(3);
  
  pinMode(flowPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(flowPin), flowISR, RISING);

  loadTurbidityCalibration(); // Muat kalibrasi SEBELUM cek sensor
  checkSensors();
}

void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  unsigned long now = millis();

  static unsigned long lastFlowCalcTime = 0;
  if (now - lastFlowCalcTime >= 1000) {
    lastFlowCalcTime = now;
    flowRateLMin = (flowPulseCount / 1.0) / 7.5;
    flowPulseCount = 0;
  }

  if (now - lastSensorUpdate >= sensorInterval) {
    lastSensorUpdate = now;
    int16_t raw1 = ads.readADC_SingleEnded(2);
    voltageTDS1 = ads.computeVolts(raw1);   
    tds1.setTemperature(temperature);
    tds1.updateByVoltage(voltageTDS1);
    tdsValue1 = tds1.getTdsValue();
    
    int16_t raw2 = ads.readADC_SingleEnded(3);
    voltageTDS2 = ads.computeVolts(raw2); 
    tds2.setTemperature(temperature);
    tds2.updateByVoltage(voltageTDS2);
    tdsValue2 = tds2.getTdsValue();
    
    int adcTurb = ads.readADC_SingleEnded(0);
    voltageTurb = ads.computeVolts(adcTurb);
    
    // Perhitungan NTU berbasis VOLTAGE
    turbidityNTU = (turbidityCalibA * voltageTurb) + turbidityCalibB;
    if (turbidityNTU < 0) turbidityNTU = 0; 

    publishSensorData();

    Serial.println("======= Sensor Debugging =======");
    Serial.printf("TDS1: %.2f ppm\n", tdsValue1);
    Serial.printf("TDS1 Voltage: %.3f V\n", voltageTDS1);
    Serial.printf("TDS2: %.2f ppm\n", tdsValue2);
    Serial.printf("TDS2 Voltage: %.3f V\n", voltageTDS2);
    Serial.printf("Turbidity Voltage: %.3f V | NTU: %.1f\n", voltageTurb, turbidityNTU);
    Serial.printf("Flow Rate: %.2f L/min\n", flowRateLMin);
  }
  
  if (now - lastWaterLevelRead >= waterLevelInterval) {
    lastWaterLevelRead = now;

    Serial.println("======= Water Level Check (1 min) =======");
    Serial.println("Menyalakan sensor level air...");
    digitalWrite(LEVEL_SENSORS_POWER_PIN, HIGH);
    delay(200);

    for (int i = 0; i < 4; i++) {
        int adc = analogRead(sensorPins[i]);
        adcLevel[i] = adc; 
        
        percent[i] = adcToPrecisePercent(adc, linear_calibrations[i]);
        category[i] = getLevelCategory(percent[i]);
        
        Serial.printf("Sensor Level %d:\n", i + 1);
        Serial.printf("   ADC Value        : %d\n", adc);
        Serial.printf("   Percent (Linear) : %d%%\n", percent[i]);
        Serial.printf("   Category         : %s\n", category[i].c_str());
        Serial.printf("   Calib (Min/Max)  : %d / %d\n", 
                      linear_calibrations[i].adc_min,
                      linear_calibrations[i].adc_max);
    }

    digitalWrite(LEVEL_SENSORS_POWER_PIN, LOW);
    Serial.println("Sensor level air dimatikan.");
    Serial.println("=========================================\n");
  }

  if (now - lastDisplayUpdate >= displayInterval) {
    lastDisplayUpdate = now;
    lcd.clear();
    switch (displayState) {
      case 0:
        lcd.setCursor(0, 0);
        lcd.print("Lv1:"); lcd.print(percent[0]); lcd.print("% "); lcd.print(category[0]);
        break;
      case 1:
        lcd.setCursor(0, 0);
        lcd.print("Lv2:"); lcd.print(percent[1]); lcd.print("% "); lcd.print(category[1]);
        break;
      case 2:
        lcd.setCursor(0, 0);
        lcd.print("Lv3:"); lcd.print(percent[2]); lcd.print("% "); lcd.print(category[0]);
        break;
      case 3:
        lcd.setCursor(0, 0);
        lcd.print("Lv4:"); lcd.print(percent[3]); lcd.print("% "); lcd.print(category[1]);
        break;
      case 4:
        lcd.setCursor(0, 0);
        lcd.print("T1:"); lcd.print(tdsValue1, 0);
        lcd.print(" T2:"); lcd.print(tdsValue2, 0);
        break;
      case 5:
        lcd.setCursor(0, 0);
        lcd.print("TUR:"); lcd.print(turbidityNTU, 1); lcd.print(" NTU");
        break;
      case 6:
        lcd.setCursor(0, 0);
        lcd.print("Flow:"); lcd.print(flowRateLMin, 2); lcd.print("L/m");
        break;
    }

    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
      char timeStr[17];
      strftime(timeStr, sizeof(timeStr), "%d/%m/%y %H:%M", &timeinfo);
      lcd.setCursor(0, 1);
      lcd.print(timeStr);
    }

    displayState = (displayState + 1) % 7;
  }

  handleSerialInput();
}