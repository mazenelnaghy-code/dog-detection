# Wiring and assembly

([العربية](WIRING.ar.md))

![Wiring diagram](images/wiring.svg)

All pin numbers in the code are **BCM GPIO numbers** (gpiozero default). The physical pin numbers
on the 40-pin header are given in brackets. Same layout on Raspberry Pi 4 and Pi 5.

| Part | Part pin | Raspberry Pi | Config key |
|---|---|---|---|
| Relay module | VCC | 5V (pin 2) | |
| | GND | GND (pin 6) | |
| | IN | **GPIO17** (pin 11) | `repeller.pin`, `repeller.active_high` |
| Buzzer module (active) | VCC | 3.3V (pin 1) | |
| | GND | GND (pin 9) | |
| | I/O | **GPIO27** (pin 13) | `buzzer.pin`, `buzzer.active_high` |
| Camera | ribbon cable | CAM/CSI connector | `camera.source: picamera` |
| 7" screen | HDMI + USB (power/touch) | micro-HDMI 0 + any USB port | `display.*` |
| Fan | 5V / GND | pin 4 / pin 14, or the Pi 5 fan connector | |

## Assembly, step by step

**Tools:** small screwdriver, multimeter (recommended), 9 female-to-female jumper wires, 2 short
wires for the 12 V side. **Rule for every step: unplug ALL power before touching any wire.**

### 1. Prepare and test the Pi alone

Flash the SD card and install the software first (see [GETTING_STARTED.md](GETTING_STARTED.md),
steps 2–4), so you know the Pi itself works before adding hardware.

✅ The Pi boots, you can log in over SSH or on the screen.

### 2. Camera

1. Find the camera connector (Pi 4: between HDMI and audio jack, marked CAMERA; Pi 5: either of
   the two small connectors, marked CAM/DISP 0 or 1).
2. Lift the connector latch gently, slide the ribbon in fully and press the latch down.
   Pi 4: the blue stiffener faces the audio jack / Ethernet side. Pi 5: use the 22-pin cable,
   narrow end into the Pi, oriented as shown in the official
   [camera guide](https://www.raspberrypi.com/documentation/accessories/camera.html). A reversed cable
   usually just is not detected, so if the check below fails, power off and flip it.

✅ `rpicam-hello --list-cameras` lists the camera. The **Camera** line of
`tools/hardware_check.py` says PASS, and `hardware_check.jpg` shows the right image.

### 3. Screen

Plug the screen's HDMI cable into **micro-HDMI 0** (the one next to the USB-C power port) and its
power/touch USB cable into any USB port of the Pi.

✅ The desktop or boot text appears on the screen.

### 4. Relay module (3 wires)

| Relay pin | → | Pi physical pin |
|---|---|---|
| VCC | → | **pin 2** (5V) |
| GND | → | **pin 6** (GND) |
| IN | → | **pin 11** (GPIO17) |

**Finding pin 1:** it is at the end of the 40-pin header **farthest from the USB ports** (its solder
pad on the underside is square). Odd pins (1, 3, 5…) are in the row nearer the middle of the board,
even pins (2, 4, 6…) in the row along the board edge. A printed GPIO reference card or
`pinout` (run it on the Pi) shows the same map.

✅ Power on, then run `tools/hardware_check.py`. During the repeller step you hear the relay
**click** and its LED lights. If the relay is ON at boot and OFF during the test, your board is
active-HIGH: set `repeller.active_high: true`.

### 5. Buzzer module (3 wires)

| Buzzer pin | → | Pi physical pin |
|---|---|---|
| VCC | → | **pin 1** (3.3V) |
| GND | → | **pin 9** (GND) |
| I/O (or S) | → | **pin 13** (GPIO27) |

✅ `tools/hardware_check.py` says **Buzzer** PASS after you confirm you heard two beeps.

### 6. Ultrasonic repeller and 12 V (with the 12 V adapter UNPLUGGED)

1. 12 V adapter **(+)** → relay **COM** screw terminal.
2. Relay **NO** screw terminal → repeller **(+)** (usually the red wire).
3. Repeller **(−)** (black) → 12 V adapter **(−)**.
4. Check with the multimeter: no connection between any 12 V wire and any Pi pin.

✅ Plug in the 12 V adapter: the repeller stays **OFF**. Press **Test repeller** on the dashboard
(or `t` in the video window): it runs for `burst_s` seconds, then stops. A bat detector or phone
spectrum app can confirm the ultrasound; a 23 kHz tone is silent to most adults.

### 7. Fan, enclosure, final check

Fit the fan (Pi 5: Active Cooler on the fan connector; Pi 4: 5 V fan on pins 4 and 14), close the
enclosure with the camera window and the repeller speaker facing outward, and run the full
`tools/hardware_check.py` once more. Everything should say PASS.


## Relay and the 12 V repeller

- The repeller's **+12 V goes through the relay's COM → NO contacts**. *Normally Open* means
  the repeller is OFF whenever the Pi is off, booting or crashed. This is the fail-safe.
- The 12 V circuit is **never connected to any Pi pin**. The relay isolates it.
- Most cheap relay boards are **active-LOW** (they switch ON when IN is pulled to GND), which is
  why the default is `repeller.active_high: false`.
- Two known problems with 5 V active-LOW boards on a 3.3 V Pi:
  - *The relay never turns off.* 3.3 V is not "high" enough for some boards. Use a board marked
    3.3 V-compatible, or one with a transistor input.
  - *The relay clicks ON while the Pi boots.* Use a **high-level trigger** board (many boards have
    an H/L jumper) and set `repeller.active_high: true`.
- Prefer an **opto-isolated** relay board. If yours has a `JD-VCC` jumper, keep it fitted unless you
  power the relay coil separately.

## Buzzer

Use an **active buzzer module** (3 pins, with its own transistor). It beeps when its input is
HIGH (`buzzer.active_high: true`). A bare buzzer draws more current than a GPIO pin may supply
(about 16 mA max), so it needs an NPN transistor (2N2222 / S8050) with a 1 kΩ base resistor.

## Camera

- **Pi 5 uses a smaller 22-pin camera connector.** Buy the Pi 5 camera cable (22-pin to 15-pin)
  for Camera Module v2/v3.
- For night use choose a **NoIR** camera plus an infrared illuminator (the pink-tinted images on
  the original poster come from a NoIR camera).
- Check it with `rpicam-hello --list-cameras`. If it is mounted upside down, set `camera.rotate: 180`.

## Power

| Supply | For |
|---|---|
| 5 V / 5 A USB-C (27 W official supply) | Raspberry Pi 5 (the original prototype used this) |
| 5 V / 3 A USB-C | Raspberry Pi 4 |
| 12 V DC adapter (current per the repeller's label, typically ≥ 1 A) | ultrasonic repeller through the relay |

The screen takes its 5 V from a Pi USB port, as in the original build. Keep the fan running: YOLO
keeps the CPU busy all the time, and a hot Pi slows itself down.
