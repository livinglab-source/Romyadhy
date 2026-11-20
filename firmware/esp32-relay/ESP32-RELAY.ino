#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_task_wdt.h>

const char* ssid = "LivingLab";
const char* password = "LABTengah2026!";
const char* mqtt_server = "192.168.88.88";
const int mqtt_port = 1883;

// MQTT Topics
const char* mqtt_topic_pompa = "smartgarden/relay/pompa_irigasi/command";
const char* mqtt_topic_kuras_tandon = "smartgarden/relay/pengurasan_tandon/command";
const char* mqtt_topic_pengaduk = "smartgarden/relay/pengaduk_tandon/command";
const char* mqtt_topic_kuras = "smartgarden/relay/pengurasan/command";
const char* mqtt_topic_valve_tandon = "smartgarden/relay/valve_tandon/command";
const char* mqtt_topic_pompa_kuras  = "smartgarden/relay/pompa_kuras/command";

// Relay Pins
const int relayPinPompa = 26;        // Irigation Pump (AC)
const int relayPinPengaduk = 25;     // Dinamo Mix (AC)
const int relayPinKurasTandon = 27;  // Draining Pump (DC)
const int relayPinKuras = 13;        // Valve Drain Out (DC)
const int relayPinValveTandon = 32;  // Valve Tandon (DC)

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastReconnectAttempt = 0;

//NOTE: Millis Timing Variables
unsigned long timerKurasTandon = 0;
int stateKurasTandon = 0;  // 0 = Idle, 1 = Waiting to Turn Pump ON, 2 = Waiting to Turn Pump OFF

unsigned long timerKuras = 0;
int stateKuras = 0;  // 0 = Idle, 1 = Waiting to Turn Pump ON, 2 = Waiting to Turn Pump OFF

const unsigned long delayTurnOn = 500;    // 0.5 seconds
const unsigned long delayTurnOff = 1500;  // 1.5 seconds

void setRelay(int pin, const char* label, const char* msg) {
  if (strcmp(msg, "1") == 0) {
    digitalWrite(pin, LOW);
    Serial.printf(">>> ON  : %s (Pin %d)\n", label, pin);
  } else if (strcmp(msg, "0") == 0) {
    digitalWrite(pin, HIGH);
    Serial.printf(">>> OFF : %s (Pin %d)\n", label, pin);
  } else {
    Serial.printf(">>> UNKNOWN command '%s' for %s\n", msg, label);
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  char message[length + 1];
  strncpy(message, (char*)payload, length);
  message[length] = '\0';
  Serial.printf("\n[MQTT] Topic: %s  Msg: %s\n", topic, message);

  if (strcmp(topic, mqtt_topic_pompa) == 0) {
    setRelay(relayPinPompa, "Pompa Irigasi", message);
  } else if (strcmp(topic, mqtt_topic_kuras_tandon) == 0) {
    if (strcmp(message, "1") == 0) {
      setRelay(relayPinKuras, "Valve Drain Out", "0");
      setRelay(relayPinValveTandon, "Valve Tandon", "1");
      stateKurasTandon = 1;
      timerKurasTandon = millis();
    } else if (strcmp(message, "0") == 0) {
      setRelay(relayPinValveTandon, "Valve Tandon", "0");
      stateKurasTandon = 2;
      timerKurasTandon = millis();
    }
    // setRelay(relayPinKurasTandon, "Pump DC", message);
    // setRelay(relayPinValveTandon, "Valve Tandon", message);
  } else if (strcmp(topic, mqtt_topic_pengaduk) == 0) {
    setRelay(relayPinPengaduk, "Pengaduk Tandon", message);
  } else if (strcmp(topic, mqtt_topic_kuras) == 0) {
    if (strcmp(message, "1") == 0) {
      setRelay(relayPinValveTandon, "Valve Tandon", "0");
      setRelay(relayPinKuras, "Valve Drain Out", "1");
      stateKuras = 1;
      timerKuras = millis();
    } else if (strcmp(message, "0") == 0) {
      setRelay(relayPinKuras, "Valve Drain Out", "0");
      stateKuras = 2;
      timerKuras = millis();
    }
    // setRelay(relayPinKurasTandon, "Pump DC", message);
    // setRelay(relayPinKuras, "Valve Drain Out", message);
  } else if (strcmp(topic, mqtt_topic_valve_tandon) == 0) {
    setRelay(relayPinValveTandon, "Valve Tandon", message);
  } else if (strcmp(topic, mqtt_topic_pompa_kuras) == 0) {
    setRelay(relayPinKurasTandon, "Pompa Kuras", message);  // ponytail: direct control, no sequencing, no interlocking
  } else {
    Serial.println("[MQTT] Topik tidak dikenali.");
  }
}

bool reconnectMQTT() {
  Serial.println("[MQTT] Mencoba reconnect...");
  if (client.connect("ESP32_Hidroponik_Client")) {
    Serial.println("[MQTT] Terhubung!");
    client.subscribe(mqtt_topic_pompa);
    client.subscribe(mqtt_topic_kuras_tandon);
    client.subscribe(mqtt_topic_pengaduk);
    client.subscribe(mqtt_topic_kuras);
    client.subscribe(mqtt_topic_valve_tandon);
    client.subscribe(mqtt_topic_pompa_kuras);
    return true;
  }
  Serial.printf("[MQTT] Gagal, rc=%d. Coba lagi 5 detik.\n", client.state());
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(100);

  // Watchdog: restart ESP32 if loop hangs for >10 seconds
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 10000,
    .idle_core_mask = 0,
    .trigger_panic = true
  };
  esp_task_wdt_reconfigure(&wdt_config);
  esp_task_wdt_add(NULL);

  // Initialize ALL 5 pins
  int pins[] = { relayPinPompa, relayPinKurasTandon, relayPinPengaduk, relayPinKuras, relayPinValveTandon };
  for (int pin : pins) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);  // Set to HIGH (OFF) on boot to prevent random activation
  }

  Serial.println("\n[SYS] Memulai ESP32 Hidroponik Controller...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("[WiFi] Connecting");

  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[WiFi] GAGAL! Restarting...");
    ESP.restart();
  }
  Serial.println("\n[WiFi] Terhubung! IP: " + WiFi.localIP().toString());

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  client.setKeepAlive(30);
  client.setSocketTimeout(5);

  reconnectMQTT();
}

void loop() {
  esp_task_wdt_reset();

  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      reconnectMQTT();
    }
  }

  client.loop();

  unsigned long currentMillis = millis();

  // 1. Check Kuras Tandon Sequence
  if (stateKurasTandon == 1 && (currentMillis - timerKurasTandon >= delayTurnOn)) {
    setRelay(relayPinKurasTandon, "Pump DC", "1");  // Time's up: Start pump
    stateKurasTandon = 0;                           // Sequence complete, reset to idle
  } else if (stateKurasTandon == 2 && (currentMillis - timerKurasTandon >= delayTurnOff)) {
    setRelay(relayPinKurasTandon, "Pump DC", "0");  // Time's up: Stop pump
    stateKurasTandon = 0;                           // Sequence complete, reset to idle
  }

  // 2. Check Kuras Sequence
  if (stateKuras == 1 && (currentMillis - timerKuras >= delayTurnOn)) {
    setRelay(relayPinKurasTandon, "Pump DC", "1");  // Time's up: Start pump
    stateKuras = 0;                                 // Sequence complete, reset to idle
  } else if (stateKuras == 2 && (currentMillis - timerKuras >= delayTurnOff)) {
    setRelay(relayPinKurasTandon, "Pump DC", "0");  // Time's up: Stop pump
    stateKuras = 0;                                 // Sequence complete, reset to idle
  }
}
