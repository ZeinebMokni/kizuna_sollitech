# QATRA second ESP32 firmware

This ESP32-WROOM-32 project is the display, SD logger and pump relay controller.
It is intentionally separate from the sensor ESP32.

## Safety model

- The pump relay starts only after a signed platform command.
- The command must include the correct farm, device, zone, signature and expiry.
- Local duration and volume limits remain enforced.
- MQTT/Wi-Fi loss stops the pump.
- The watchdog stops the pump on firmware failure.
- The second ESP32 must not infer and start a pump cycle from soil thresholds.
- The existing hardware emergency stop must remain independent of MQTT and software.

## Sensors and display

- LCD 16x4 over PCF8574 I2C
- MicroSD card
- Temperature, humidity, soil moisture, water level and flow status are received
  from the QATRA MQTT telemetry topics
- Buzzer and LEDs are indicators only

## Setup

```powershell
cd firmware/esp32-qatra2
copy include\qatra_config.h.example include\qatra_config.h
python -m platformio run
python -m platformio run --target upload
python -m platformio device monitor
```

Fill in real Wi-Fi, MQTT, API-key, HMAC-secret and UUID values before use.
Never commit `include/qatra_config.h`.
