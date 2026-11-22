# ESP32-WROOM-32 wiring

This is a prototype bench layout. Verify every voltage and polarity with a
multimeter before connecting the ESP32 or a powered load.

## ESP32 and sensors

| Component | ESP32-WROOM-32 connection |
|---|---|
| Capacitive soil moisture | Signal -> GPIO34 (ADC), 3.3 V -> sensor, GND -> GND |
| DHT22 | Data -> GPIO27, 3.3 V -> sensor, GND -> GND |
| YF-S201 flow pulse | Signal -> GPIO26, 5 V or regulated supply, GND -> GND |
| Tank float | Signal -> GPIO25, GND when active, 10k pull-up |
| Emergency stop | Normally-open contacts -> GPIO33 and GND, 10k pull-up |
| DC pump MOSFET gate | GPIO32 -> gate resistor 220 ohm |
| Battery ADC | Battery point -> voltage divider -> GPIO35 |
| Solar ADC | Solar point -> voltage divider -> GPIO36 |

GPIO25 and GPIO33 should be used as defined below:

- Float active state is configurable; the default expects LOW.
- Emergency-stop active state is configurable; the default expects LOW.
- GPIO34 is input only and suitable for the capacitive soil sensor.
- GPIO35 and GPIO36 are ADC inputs.

Do not connect 5 V directly to ESP32 GPIO pins.

## DC pump MOSFET

Use a logic-level N-channel MOSFET rated above:

- Battery voltage
- Stall/starting pump current
- Continuous pump current
- Pulse and derating temperature

Suggested low-side wiring:

```text
Battery negative -> pump negative -> MOSFET drain
MOSFET source -> battery negative
GPIO32 -> 220 ohm -> MOSFET gate
MOSFET gate -> 100k resistor -> battery negative
Pump positive -> battery positive
Fuse -> battery positive
Flyback/snubber -> across inductive or motor load as required
```

The ESP32 and pump must share a common ground. Use an external regulated
driver supply and isolation if the pump transients could reset the controller.

## Solar and battery

Recommended chain:

```text
6 V solar panel -> CN3065 charging input
CN3065 battery output -> protected 3.7 V Li-ion
Li-ion -> MT3608 boost -> 5 V for ESP32 and sensors
Li-ion -> protected high-side switch/fuse -> pump
```

The USB, CN3065 and boost converter grounds must be common only according to
the board manufacturer's connection diagram. The battery must include an
integrated or external protection circuit.

ADC battery and solar measurements require a divider that keeps ESP32 ADC
input below 3.3 V. A 2:1 divider is only a starting point, not a guarantee.
Measure the divider output before energising the controller.

## DHT22

Use GPIO27 with the data pull-up required by the sensor. Keep the cable short.

## YF-S201

The pulse count is initially converted using 450 pulses per litre. This value
must be calibrated using a measured container or a reference flow meter.

## Emergency stop

The emergency-stop circuit must be independent of MQTT and independent of
software:

- Normally-open or normally-closed contact choice must match the installed
  fail-safe circuit.
- Cutting the emergency circuit must de-energise the pump MOSFET driver.
- MQTT loss, Wi-Fi loss and watchdog reset must stop the pump.

Bench testing must start with the pump disconnected. Test MOSFET switching
and local stop logic before reconnecting a powered load.
