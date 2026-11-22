#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <esp_task_wdt.h>
#include <mbedtls/md.h>
#include <time.h>

#include <qatra_config.h>

namespace {

String hmacSha256Hex(const String &data, const char *secret);
bool hmacEquals(const char *a, const char *b);
void stopPump(const char *reason);

constexpr uint32_t TELEMETRY_INTERVAL_MS = 5000;
constexpr uint32_t COMMAND_TIMEOUT_MS = 300000;
constexpr uint32_t MQTT_RECONNECT_MS = 5000;
constexpr float FLOW_PULSES_PER_LITER = 450.0f;
constexpr float BATTERY_DIVIDER_RATIO = 2.0f;
constexpr float SOLAR_DIVIDER_RATIO = 2.0f;
constexpr float ADC_REF_VOLTAGE = 3.3f;
constexpr int ADC_MAX = 4095;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

volatile uint32_t flowPulseCount = 0;
volatile uint32_t lastFlowPulseMs = 0;
uint32_t flowWindowStartMs = 0;
uint32_t flowWindowPulseStart = 0;
uint32_t telemetryStartMs = 0;
uint32_t pumpStartedMs = 0;
uint32_t pumpUntilMs = 0;
float commandedMaxVolumeM3 = 0.0f;
float measuredVolumeM3 = 0.0f;
String activeCommandId;
bool pumpRunning = false;
bool mqttConnectedOnce = false;

void IRAM_ATTR onFlowPulse() {
  flowPulseCount = flowPulseCount + 1;
  lastFlowPulseMs = millis();
}

bool sht21ReadRaw(uint8_t command, uint16_t &raw) {
  constexpr uint8_t SHT21_ADDRESS = 0x40;
  Wire.beginTransmission(SHT21_ADDRESS);
  Wire.write(command);
  if (Wire.endTransmission() != 0) return false;
  delay(100);
  if (Wire.requestFrom((uint8_t)SHT21_ADDRESS, (uint8_t)3) != 3) return false;
  const uint8_t msb = Wire.read();
  const uint8_t lsb = Wire.read();
  Wire.read();
  raw = (((uint16_t)msb << 8) | lsb) & 0xFFFC;
  return true;
}

float readWaterLevelPercent() {
  const int raw = analogRead(PIN_WATER_ADC);
  const float percent =
      (raw - WATER_ADC_EMPTY) * 100.0f /
      (float)(WATER_ADC_FULL - WATER_ADC_EMPTY);
  return constrain(percent, 0.0f, 100.0f);
}

void stopPump(const char *reason) {
  pumpRunning = false;
  pumpUntilMs = 0;
  digitalWrite(PIN_PUMP_MOSFET, PUMP_ACTIVE_HIGH ? LOW : HIGH);
  Serial.printf("Pump stopped: %s\n", reason);
}

void startPump(uint32_t durationMs, float maxVolumeM3) {
  const float tankPercent = readWaterLevelPercent();
  const bool tankClear = tankPercent >= TANK_MIN_PERCENT;
  bool emergencyClear = EMERGENCY_STOP_ACTIVE_LOW
                            ? digitalRead(PIN_EMERGENCY_STOP) == HIGH
                            : digitalRead(PIN_EMERGENCY_STOP) == LOW;

  if (!tankClear) {
    stopPump("tank float is active");
    return;
  }
  if (!emergencyClear) {
    stopPump("emergency stop is active");
    return;
  }
  if (!mqtt.connected()) {
    stopPump("MQTT connection lost");
    return;
  }

  pumpRunning = true;
  pumpStartedMs = millis();
  pumpUntilMs = millis() + durationMs;
  commandedMaxVolumeM3 = maxVolumeM3;
  measuredVolumeM3 = 0.0f;
  digitalWrite(PIN_PUMP_MOSFET, PUMP_ACTIVE_HIGH ? HIGH : LOW);
}

String mqttMeasurementTopic(const char *sensorId) {
  return String("qatra/") + FARM_UUID + "/" + DEVICE_UUID +
         "/measurements/" + sensorId;
}

String mqttAckTopic(const char *commandId) {
  return String("qatra/") + FARM_UUID + "/" + DEVICE_UUID +
         "/ack/" + commandId;
}

String mqttCommandTopic() {
  return String("qatra/") + FARM_UUID + "/" + DEVICE_UUID +
         "/commands/" + ZONE_UUID;
}

bool publishJson(const String &topic, JsonDocument &doc) {
  char payload[768];
  size_t length = serializeJson(doc, payload, sizeof(payload));
  if (!mqtt.publish(topic.c_str(), (const uint8_t *)payload, length, false)) {
    return false;
  }
  return true;
}

void publishMeasurement(const char *sensorId, float value, const char *unit,
                        const char *quality, const char *qualityNote) {
  if (!mqtt.connected()) return;
  time_t now = time(nullptr);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));

  JsonDocument doc;
  doc["api_key"] = MQTT_DEVICE_API_KEY;
  doc["observed_at"] = timestamp;
  doc["value"] = value;
  doc["unit"] = unit;
  doc["quality"] = quality;
  doc["quality_note"] = qualityNote;
  doc["idempotency_key"] = String(sensorId) + "-" + String((uint32_t)now);
  publishJson(mqttMeasurementTopic(sensorId), doc);
}

float soilMoisturePercent() {
  const int raw = analogRead(PIN_SOIL_ADC);
  const float percentage = (SOIL_ADC_DRY - raw) * 100.0f /
                           (float)(SOIL_ADC_DRY - SOIL_ADC_WET);
  return constrain(percentage, 0.0f, 100.0f);
}

float adcVoltage(int pin, float dividerRatio) {
  const int raw = analogRead(pin);
  return (raw / (float)ADC_MAX) * ADC_REF_VOLTAGE * dividerRatio;
}

float flowM3h() {
  const uint32_t now = millis();
  if (flowWindowStartMs == 0) {
    flowWindowStartMs = now;
    flowWindowPulseStart = flowPulseCount;
    return 0.0f;
  }
  const uint32_t elapsed = now - flowWindowStartMs;
  if (elapsed < 1000) return 0.0f;
  noInterrupts();
  uint32_t pulses = flowPulseCount - flowWindowPulseStart;
  interrupts();
  const float litersPerMinute =
      ((pulses / FLOW_PULSES_PER_LITER) / (elapsed / 60000.0f));
  flowWindowStartMs = now;
  flowWindowPulseStart = flowPulseCount;
  return litersPerMinute * 0.06f;
}

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
  for (int i = 0; i < 32; i++) {
    snprintf(&hex[i * 2], 3, "%02x", digest[i]);
  }
  return String(hex);
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

void publishAck(const char *commandId, const char *status, const char *detail) {
  JsonDocument doc;
  doc["api_key"] = MQTT_DEVICE_API_KEY;
  doc["status"] = status;
  doc["detail"] = detail;
  time_t now = time(nullptr);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));
  doc["observed_at"] = timestamp;
  String topic = mqttAckTopic(commandId);
  publishJson(topic, doc);
}

String canonicalJsonNumber(float value) {
  String number = String(value, 6);
  while (number.length() > 1 && number.endsWith("0")) {
    number.remove(number.length() - 1);
  }
  if (number.endsWith(".")) number += "0";
  return number;
}

void handleCommand(char *topic, byte *payload, unsigned int length) {
  if (length > 1024) {
    stopPump("oversized command");
    return;
  }
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    stopPump("invalid command JSON");
    return;
  }

  const char *commandId = doc["command_id"];
  const char *expiresAt = doc["expires_at"];
  const char *signature = doc["signature"];
  const char *deviceId = doc["device_id"];
  const char *zoneId = doc["zone_id"];
  const char *action = doc["action"];
  if (!commandId || !expiresAt || !signature || !deviceId || !zoneId || !action) {
    stopPump("missing command fields");
    return;
  }
  if (strcmp(deviceId, DEVICE_UUID) != 0 || strcmp(zoneId, ZONE_UUID) != 0) {
    stopPump("command is not for this device and zone");
    return;
  }

  const time_t expires = parseUtc(expiresAt);
  if (expires == 0 || expires <= time(nullptr)) {
    publishAck(commandId, "rejected", "command expired");
    stopPump("command expired");
    return;
  }

  // Server canonical JSON is sorted and compact. Rebuild explicitly for exact parity.
  String canonical =
      "{\"action\":\"" + String(action) +
      "\",\"command_id\":\"" + String(commandId) +
      "\",\"device_id\":\"" + String(deviceId) +
      "\",\"duration_s\":" + (doc["duration_s"].isNull() ? "null" : String(doc["duration_s"].as<int>())) +
      ",\"expires_at\":\"" + String(expiresAt) +
      "\",\"farm_id\":\"" + String(doc["farm_id"].as<const char *>()) +
      "\",\"max_volume_m3\":" + (doc["max_volume_m3"].isNull() ? "null" : canonicalJsonNumber(doc["max_volume_m3"].as<float>())) +
      ",\"zone_id\":\"" + String(zoneId) + "\"}";

  const String expected = hmacSha256Hex(canonical, MQTT_COMMAND_SECRET);
  if (!hmacEquals(expected.c_str(), signature)) {
    publishAck(commandId, "rejected", "invalid command signature");
    stopPump("invalid command signature");
    return;
  }

  if (strcmp(action, "emergency_stop") == 0 ||
      strcmp(action, "stop_pump") == 0 ||
      strcmp(action, "close_valve") == 0) {
    stopPump("approved stop command");
    publishAck(commandId, "stopped", "pump stopped");
    return;
  }

  if (strcmp(action, "start_pump") != 0 &&
      strcmp(action, "open_valve") != 0) {
    publishAck(commandId, "rejected", "unsupported action");
    return;
  }

  int durationS = doc["duration_s"].isNull() ? 0 : doc["duration_s"].as<int>();
  float maxVolumeM3 = doc["max_volume_m3"].isNull()
                          ? 0.0f
                          : doc["max_volume_m3"].as<float>();
  if (durationS <= 0 || durationS > 2700) {
    publishAck(commandId, "rejected", "duration exceeds local limit");
    return;
  }
  if (maxVolumeM3 > 100.0f) {
    publishAck(commandId, "rejected", "volume exceeds local limit");
    return;
  }

  activeCommandId = commandId;
  startPump((uint32_t)durationS * 1000, maxVolumeM3);
  if (pumpRunning) {
    publishAck(commandId, "started", "pump started with local limits");
  } else {
    publishAck(commandId, "rejected", "local safety interlock prevented start");
  }
}

bool hmacEquals(const char *a, const char *b) {
  if (strlen(a) != strlen(b)) return false;
  uint8_t diff = 0;
  for (size_t i = 0; i < strlen(a); i++) diff |= (uint8_t)a[i] ^ (uint8_t)b[i];
  return diff == 0;
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  handleCommand(topic, payload, length);
}

void reconnectMqtt() {
  static uint32_t lastAttempt = 0;
  if (mqtt.connected()) return;
  if (millis() - lastAttempt < MQTT_RECONNECT_MS) return;
  lastAttempt = millis();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  const String clientId = String("qatra-") + DEVICE_UUID;
  if (mqtt.connect(clientId.c_str())) {
    mqttConnectedOnce = true;
    mqtt.subscribe(mqttCommandTopic().c_str(), 1);
  }
}

void publishTelemetry() {
  const float soil = soilMoisturePercent();
  publishMeasurement(SOIL_SENSOR_ID, soil, "%", "valid", "capacitive ADC; calibration required");

  uint16_t tempRaw = 0;
  uint16_t humidityRaw = 0;
  if (sht21ReadRaw(0xE3, tempRaw) && sht21ReadRaw(0xE5, humidityRaw)) {
    const float temperature = -46.85f + 175.72f * tempRaw / 65536.0f;
    const float humidity =
        constrain(-6.0f + 125.0f * humidityRaw / 65536.0f, 0.0f, 100.0f);
    publishMeasurement("sht21-temperature-1", temperature, "degC", "valid", "SHT21");
    publishMeasurement("sht21-humidity-1", humidity, "%", "valid", "SHT21");
  } else {
    publishMeasurement("sht21-temperature-1", 0.0f, "degC", "missing", "SHT21 read failed");
    publishMeasurement("sht21-humidity-1", 0.0f, "%", "missing", "SHT21 read failed");
  }

  const float flow = flowM3h();
  publishMeasurement(FLOW_SENSOR_ID, flow, "m3/h", "valid", "YF-S201 pulse count");

  const float waterLevel = readWaterLevelPercent();
  publishMeasurement(LEVEL_SENSOR_ID, waterLevel, "%",
                     "valid", "water level ADC; calibration required");

  publishMeasurement("battery-voltage-1",
                     adcVoltage(PIN_BATTERY_ADC, BATTERY_DIVIDER_RATIO),
                     "V", "valid", "ADC estimate");
  publishMeasurement("solar-voltage-1",
                     adcVoltage(PIN_SOLAR_ADC, SOLAR_DIVIDER_RATIO),
                     "V", "valid", "ADC estimate");
}

} // namespace

void setup() {
  Serial.begin(115200);
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setTimeOut(200);
  analogSetPinAttenuation(PIN_SOIL_ADC, ADC_11db);
  analogSetPinAttenuation(PIN_WATER_ADC, ADC_11db);
  analogSetPinAttenuation(PIN_BATTERY_ADC, ADC_11db);
  analogSetPinAttenuation(PIN_SOLAR_ADC, ADC_11db);
  pinMode(PIN_EMERGENCY_STOP,
          EMERGENCY_STOP_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
  pinMode(PIN_PUMP_MOSFET, OUTPUT);
  digitalWrite(PIN_PUMP_MOSFET, PUMP_ACTIVE_HIGH ? LOW : HIGH);
  pinMode(PIN_FLOW_PULSE, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_PULSE), onFlowPulse, RISING);
  analogReadResolution(12);
  esp_task_wdt_config_t wdtConfig = {
      .timeout_ms = 30000,
      .idle_core_mask = (1u << 0) | (1u << 1),
      .trigger_panic = true,
  };
  esp_task_wdt_init(&wdtConfig);
  esp_task_wdt_add(nullptr);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTzTime("UTC0", "pool.ntp.org");

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
}

void loop() {
  esp_task_wdt_reset();
  if (WiFi.status() != WL_CONNECTED) {
    stopPump("Wi-Fi disconnected");
  } else {
    reconnectMqtt();
  }
  mqtt.loop();

  const bool emergencyActive = EMERGENCY_STOP_ACTIVE_LOW
                                   ? digitalRead(PIN_EMERGENCY_STOP) == LOW
                                   : digitalRead(PIN_EMERGENCY_STOP) == HIGH;
  const bool tankLow = readWaterLevelPercent() < TANK_MIN_PERCENT;
  if (emergencyActive) stopPump("emergency stop input active");
  if (tankLow) stopPump("tank level below local minimum");

  if (pumpRunning && millis() >= pumpUntilMs) {
    stopPump("approved duration elapsed");
  }
  if (pumpRunning && measuredVolumeM3 >= commandedMaxVolumeM3 &&
      commandedMaxVolumeM3 > 0) {
    stopPump("measured volume limit reached");
  }

  if (pumpRunning) {
    const float flow = flowM3h();
    measuredVolumeM3 += flow * (TELEMETRY_INTERVAL_MS / 3600000.0f);
  }

  if (mqtt.connected() && millis() - telemetryStartMs >= TELEMETRY_INTERVAL_MS) {
    telemetryStartMs = millis();
    publishTelemetry();
  }

  delay(10);
}
