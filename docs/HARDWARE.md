# Hardware (bill of materials)

The parts used by the original prototype, with notes on choosing each one.

| # | Part | Notes |
|---|---|---|
| 1 | **Raspberry Pi 5** (4 GB+) or Pi 4 (4 GB) | Pi 5 is about 2–3× faster for YOLO. |
| 2 | microSD card, 32 GB+, A1/A2 | Raspberry Pi OS 64-bit (Bookworm or newer) |
| 3 | **Camera:** Camera Module 3 or v2 | NoIR version + IR illuminator for night; Pi 5 needs the 22-pin cable |
| 4 | **7" HDMI display** | powered from a Pi USB port; micro-HDMI cable |
| 5 | **1-channel relay module**, opto-isolated | 3.3 V-compatible or high/low-level selectable (see WIRING.md) |
| 6 | **Ultrasonic dog repeller module, 12 V** | the device that actually repels; see below |
| 7 | **Active buzzer module** | audible alert for people |
| 8 | 12 V DC adapter | sized for the repeller |
| 9 | 5 V 5 A USB-C supply (Pi 5) or 5 V 3 A (Pi 4) | the original build used 5 V/5 A |
| 10 | Cooling: Pi 5 Active Cooler or 5 V fan + heatsinks | YOLO keeps the CPU busy constantly |
| 11 | Vented enclosure + tripod/mount | camera window and repeller speaker facing outward |
| 12 | Jumper wires, USB/HDMI extension cables | extensions bring ports to the outside of the box |

## Choosing the ultrasonic repeller

- Pick a module with an **adjustable or fixed frequency of 23–25 kHz**. Dogs hear up to about
  45 kHz, while young children can hear close to 20 kHz, so staying above about 23 kHz keeps it
  inaudible to children. Avoid "sonic" modes that are audible to people.
- **Directional** transducers aimed at the danger zone work best. Mount the box at roughly
  dog-head height, pointed where dogs approach.
- Effective range is typically 5–10 m. Match `zone.danger_distance_m` and the zone rectangle to it.
- An **HC-SR04 distance sensor** also emits ultrasound (40 kHz), but it is far too weak to repel
  a dog. Use a real repeller module.

## Placement tips

- A camera looking slightly down at the ground sees close dogs in the **lower part** of the
  image, which is why the default danger zone covers the lower-middle of the frame.
- Avoid pointing the camera straight into the sun or at moving trees and flags.
- Run the system on the real site for a day with `hardware.backend: sim`, the zone drawn on the
  screen, and watch the log. Then adjust `zone.rect` before arming the real repeller.
