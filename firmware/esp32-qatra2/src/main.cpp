#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <LiquidCrystal_I2C.h>
#include <SPI.h>
#include <SD.h>
#include <Wire.h>
#include <esp_task_wdt.h>
#include <mbedtls/md.h>
#include <time.h>

#include <qatra_config.h>

namespace {

constexpr uint32_t MQTT_RECONNECT_MS = 5000;
constexpr uint32_t DISPLAY_INTERVAL_MS = 500;
constexpr uint32_t TELEMETRY_TIMEOUT_MS = 15000;
constexpr uint32_t MAX_PUMP_DURATION_S = 2700;
constexpr float MAX_PUMP_VOLUME_M3 = 100.0f;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
LiquidCrystal_I2C lcd(LCD_ADDRESS, LCD_COLUMNS, LCD_ROWS);

float temperature = 0.0f;
float humidity = 0.0f;
float soilMoisture = 0.0f;
float tankLevel = 0.0f;
float flowM3h = 0.0f;
uint32_t lastTelemetryMs = 0;

bool pumpRunning = false;
uint32_t pumpStartedMs = 0;
uint32_t pumpUntilMs = 0;
float maxVolumeM3 = 0.0f;
float measuredVolumeM3 = 0.0f;
bool sdReady = false;

String hmacSha256Hex(const String &data, const char *secret) {
  uint8_t digest[32];
  mbedtls_md_context_t context;
  mbedtls_md_init(&context);
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_setup(&context, info, 1);
  mbedtls_md_hmac_starts(&context, (const uint8_t *)secret, strlen(secret));
  mbedtls_md_hmac_update(&context, (const uint8_t *)data.c_str(), data.length());
  mbedtls_md_hmac_finish(&context, digest);
  mbedtls_md_free(&context);

  char hex[65];
  for (int i = 0; i < 32; i++) snprintf(&hex[i * 2], 3, "%02x", digest[i]);
  return String(hex);
}

bool hmacEquals(const char *a, const char *b) {
  if (strlen(a) != strlen(b)) return false;
  uint8_t diff = 0;
  for (size_t i = 0; i < strlen(a); i++) diff |= (uint8_t)a[i] ^ (uint8_t)b[i];
  return diff == 0;
}

time_t parseUtc(const String &value) {
  int year, month, day, hour, minute, second;
  if (sscanf(value.c_str(), "%d-%d-%dT%d:%d:%d",
             &year, &month, &day, &hour, &minute, &second) != 6) {
    return 0;
  }
  struct tm tm = {};
  tm.tm_year = year - 1900;
  tm.tm_mon = month - 1;
  tm.tm_mday = day;
  tm.tm_hour = hour;
  tm.tm_min = minute;
  tm.tm_sec = second;
  tm.tm_isdst = 0;
  setenv("TZ", "UTC0", 1);
  tzset();
  return mktime(&tm);
}

String canonicalJsonNumber(float value) {
  String number = String(value, 6);
  while (number.length() > 1 && number.endsWith("0")) number.remove(number.length() - 1);
  if (number.endsWith(".")) number += "0";
  return number;
}

void stopPump(const char *reason) {
  pumpRunning = false;
  pumpUntilMs = 0;
  digitalWrite(PIN_PUMP_RELAY, PUMP_ACTIVE_HIGH ? LOW : HIGH);
  Serial.printf("Pump stopped: %s\n", reason);
}

void startPump(uint32_t durationS, float volumeM3) {
  if (!mqtt.connected()) {
    stopPump("MQTT connection lost");
    return;
  }
  if (millis() - lastTelemetryMs > TELEMETRY_TIMEOUT_MS) {
    stopPump("telemetry timeout");
    return;
  }
  if (tankLevel < 20.0f) {
    stopPump("tank level below 20 percent");
    return;
  }
  pumpRunning = true;
  pumpStartedMs = millis();
  pumpUntilMs = millis() + durationS * 1000UL;
  maxVolumeM3 = volumeM3;
  measuredVolumeM3 = 0.0f;
  digitalWrite(PIN_PUMP_RELAY, PUMP_ACTIVE_HIGH ? HIGH : LOW);
}

bool publishJson(const String &topic, JsonDocument &doc) {
  char payload[512];
  const size_t length = serializeJson(doc, payload, sizeof(payload));
  return mqtt.publish(topic.c_str(), (const uint8_t *)payload, length, false);
}

void publishAck(const char *commandId, const char *status, const char *detail) {
  JsonDocument doc;
  doc["api_key"] = MQTT_DEVICE_API_KEY;
  doc["status"] = status;
  doc["detail"] = detail;
  time_t now = time(nullptr);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
  doc["observed_at"] = timestamp;
  String topic = String("qatra/") + FARM_UUID + "/" + DEVICE_UUID +
                 "/ack/" + commandId;
  publishJson(topic, doc);
}

void handleCommand(byte *payload, unsigned int length) {
  if (length > 1024) {
    stopPump("oversized command");
    return;
  }
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) {
    stopPump("invalid command JSON");
    return;
  }

  const char *commandId = doc["command_id"];
  const char *expiresAt = doc["expires_at"];
  const char *signature = doc["signature"];
  const char *farmId = doc["farm_id"];
  const char *deviceId = doc["device_id"];
  const char *zoneId = doc["zone_id"];
  const char *action = doc["action"];
  if (!commandId || !expiresAt || !signature || !farmId || !deviceId ||
      !zoneId || !action) {
    stopPump("missing command fields");
    return;
  }
  if (strcmp(farmId, FARM_UUID) != 0 ||
      strcmp(deviceId, DEVICE_UUID) != 0 ||
      strcmp(zoneId, ZONE_UUID) != 0) {
    stopPump("command has wrong identifiers");
    return;
  }

  const time_t expires = parseUtc(expiresAt);
  if (expires == 0 || expires <= time(nullptr)) {
    publishAck(commandId, "rejected", "command expired");
    stopPump("command expired");
    return;
  }

  String canonical =
      "{\"action\":\"" + String(action) +
      "\",\"command_id\":\"" + String(commandId) +
      "\",\"device_id\":\"" + String(deviceId) +
      "\",\"duration_s\":" + (doc["duration_s"].isNull() ? "null" : String(doc["duration_s"].as<int>())) +
      ",\"expires_at\":\"" + String(expiresAt) +
      "\",\"farm_id\":\"" + String(farmId) +
      "\",\"max_volume_m3\":" + (doc["max_volume_m3"].isNull() ? "null" : canonicalJsonNumber(doc["max_volume_m3"].as<float>())) +
      ",\"zone_id\":\"" + String(zoneId) + "\"}";

  const String expected = hmacSha256Hex(canonical, MQTT_COMMAND_SECRET);
  if (!hmacEquals(expected.c_str(), signature)) {
    publishAck(commandId, "rejected", "invalid signature");
    stopPump("invalid command signature");
    return;
  }

  if (strcmp(action, "stop_pump") == 0 ||
      strcmp(action, "close_valve") == 0 ||
      strcmp(action, "emergency_stop") == 0) {
    stopPump("approved stop command");
    publishAck(commandId, "stopped", "pump stopped");
    return;
  }
  if (strcmp(action, "start_pump") != 0 && strcmp(action, "open_valve") != 0) {
    publishAck(commandId, "rejected", "unsupported action");
    return;
  }

  const int durationS = doc["duration_s"].isNull() ? 0 : doc["duration_s"].as<int>();
  const float volumeM3 = doc["max_volume_m3"].isNull()
                             ? 0.0f
                             : doc["max_volume_m3"].as<float>();
  if (durationS <= 0 || durationS > MAX_PUMP_DURATION_S) {
    publishAck(commandId, "rejected", "duration exceeds local limit");
    return;
  }
  if (volumeM3 > MAX_PUMP_VOLUME_M3) {
    publishAck(commandId, "rejected", "volume exceeds local limit");
    return;
  }

  startPump(durationS, volumeM3);
  if (pumpRunning) publishAck(commandId, "started", "pump started with local limits");
  else publishAck(commandId, "rejected", "local safety interlock prevented start");
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String topicString(topic);
  String prefix = String("qatra/") + FARM_UUID + "/" + DEVICE_UUID + "/commands/";
  if (topicString.startsWith(prefix)) {
    handleCommand(payload, length);
    return;
  }

  // Sensor ESP32 JSON telemetry, or legacy display payload, updates the LCD/SD state.
  JsonDocument doc;
  if (!deserializeJson(doc, payload, length)) {
    lastTelemetryMs = millis();
    if (doc["value"].is<float>() && topicString.indexOf("measurements/") >= 0) {
      const String sensorTopic = topicString;
      const float value = doc["value"].as<float>();
      if (sensorTopic.endsWith("/temperature") || sensorTopic.endsWith("sht21-temperature-1"))
        temperature = value;
      else if (sensorTopic.endsWith("/humidity") || sensorTopic.endsWith("sht21-humidity-1"))
        humidity = value;
      else if (sensorTopic.endsWith("soil-probe-1"))
        soilMoisture = value;
      else if (sensorTopic.endsWith("tank-level-1") || sensorTopic.endsWith("tank-float-1"))
        tankLevel = value;
      else if (sensorTopic.endsWith("flow-yf-s201-1"))
        flowM3h = value;
    }
  }
}

void reconnectMqtt() {
  static uint32_t lastAttempt = 0;
  if (mqtt.connected()) return;
  if (millis() - lastAttempt < MQTT_RECONNECT_MS) return;
  lastAttempt = millis();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  const String clientId = String("qatra-display-") + DEVICE_UUID;
  if (mqtt.connect(clientId.c_str())) {
    mqtt.subscribe((String("qatra/") + FARM_UUID + "/" + DEVICE_UUID +
                    "/commands/" + ZONE_UUID).c_str());
    mqtt.subscribe("qatra/+/+/measurements/+");
  }
}

void refreshLcd() {
  char line[17];
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("QATRA SOLITECH");
  lcd.setCursor(0, 1);
  snprintf(line, sizeof(line), "T%.1fC H%.0f%%", temperature, humidity);
  lcd.print(line);
  lcd.setCursor(0, 2);
  snprintf(line, sizeof(line), "Sol%.0f%% Eau%.0f%%", soilMoisture, tankLevel);
  lcd.print(line);
  lcd.setCursor(0, 3);
  snprintf(line, sizeof(line), "D%.1f Pompe%s", flowM3h,
           pumpRunning ? "ON" : "OFF");
  lcd.print(line);
}

void sdLog() {
  if (!sdReady) return;
  File file = SD.open("/QATRA.CSV", FILE_APPEND);
  if (!file) return;
  file.printf("%lu,%.1f,%.1f,%.1f,%.1f,%.1f,%d\n",
              millis() / 1000UL, temperature, humidity, soilMoisture,
              tankLevel, flowM3h, pumpRunning ? 1 : 0);
  file.close();
}

} // namespace

void setup() {
  Serial.begin(115200);
  Wire.begin(PIN_SDA, PIN_SCL);
  lcd.init();
  lcd.backlight();

  pinMode(PIN_LED_TEMP, OUTPUT);
  pinMode(PIN_LED_SOIL, OUTPUT);
  pinMode(PIN_LED_WATER, OUTPUT);
  pinMode(PIN_LED_OK, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_PUMP_RELAY, OUTPUT);
  digitalWrite(PIN_PUMP_RELAY, PUMP_ACTIVE_HIGH ? LOW : HIGH);

  SPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, PIN_SD_CS);
  sdReady = SD.begin(PIN_SD_CS);
  if (sdReady && !SD.exists("/QATRA.CSV")) {
    File file = SD.open("/QATRA.CSV", FILE_WRITE);
    if (file) {
      file.println("temps_s,temp_C,hum_pct,sol_pct,eau_pct,debit_m3h,pompe");
      file.close();
    }
  }

  esp_task_wdt_config_t wdtConfig = {
      .timeout_ms = 30000,
      .idle_core_mask = (1u << 0) | (1u << 1),
      .trigger_panic = true,
  };
  esp_task_wdt_init(&wdtConfig);
  esp_task_wdt_add(nullptr);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
}

void loop() {
  esp_task_wdt_reset();
  if (WiFi.status() != WL_CONNECTED) stopPump("Wi-Fi disconnected");
  else reconnectMqtt();
  mqtt.loop();

  if (pumpRunning && millis() >= pumpUntilMs)
    stopPump("approved duration elapsed");
  if (pumpRunning && measuredVolumeM3 >= maxVolumeM3 && maxVolumeM3 > 0)
    stopPump("measured volume limit reached");
  static uint32_t lastVolumeMs = 0;
  if (pumpRunning) {
    const uint32_t now = millis();
    if (lastVolumeMs == 0) lastVolumeMs = now;
    const float elapsedHours =
        (now - lastVolumeMs) / 3600000.0f;
    measuredVolumeM3 += flowM3h * elapsedHours;
    lastVolumeMs = now;
  } else {
    lastVolumeMs = 0;
  }

  static uint32_t lastDisplay = 0;
  if (millis() - lastDisplay >= DISPLAY_INTERVAL_MS) {
    lastDisplay = millis();
    refreshLcd();
  }

  static uint32_t lastLog = 0;
  if (millis() - lastLog >= 10000) {
    lastLog = millis();
    sdLog();
  }

  digitalWrite(PIN_LED_OK, mqtt.connected() ? HIGH : LOW);
  delay(10);
}
