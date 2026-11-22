# QATRA ESP32-WROOM-32 firmware

This firmware is an MQTT telemetry and safety-limited pump controller prototype.
It does not connect to QATRA until Wi-Fi, MQTT and sensor calibration are configured.

## Hardware

- ESP32-WROOM-32
- Capacitive soil-moisture sensor
- DHT22
- YF-S201 pulse flow meter
- Water-level float
- DC pump with a low-side MOSFET driver
- 6 V, 3.5 W panel
- CN3065 charger
- 3.7 V Li-ion battery
- MT3608 boost converter
- Normally-open emergency stop to GPIO

## Safety

- The pump relay/MOSFET is off at reset.
- MQTT loss stops the pump.
- Wi-Fi loss stops the pump.
- Emergency-stop input stops the pump.
- Tank-level float stops the pump.
- Duration and volume limits are enforced on the firmware.
- Commands expire after the server expiry timestamp.
- Commands require a matching HMAC-SHA256 signature.
- The test broker is anonymous and must not be used in the field.
- TLS, MQTT authentication and ACLs are required for production.

## Setup

```powershell
cd firmware/esp32-qatra
copy include\qatra_config.h.example include\qatra_config.h
python -m platformio run
.\upload.ps1
python -m platformio device monitor
```

If `upload.ps1` cannot find a port, connect the ESP32 and run:

```powershell
python -m platformio device list
python -m platformio run --target upload --upload-port COM5
```

Replace `COM5` with the detected serial port.

Install PlatformIO Core or use PlatformIO in VS Code.

Before uploading, fill in `include/qatra_config.h`, especially:

- Wi-Fi credentials
- MQTT host
- device API key
- command HMAC secret
- UUIDs
- GPIO pins
- soil ADC wet/dry calibration
- flow-meter pulse calibration

The MQTT command secret must remain the same secure secret used by the server.
- Do not commit `include/qatra_config.h`.

See [WIRING.md](WIRING.md) before connecting hardware.

## Topics

Telemetry:

```text
qatra/{farm_uuid}/{device_uuid}/measurements/{sensor_id}
```

Command:

```text
qatra/{farm_uuid}/{device_uuid}/commands/{zone_uuid}
```

Acknowledgement:

```text
qatra/{farm_uuid}/{device_uuid}/ack/{command_uuid}
```
