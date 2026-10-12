# Getting started: from zero to a working device

([العربية](GETTING_STARTED.ar.md))

This guide takes you through everything in order. You do not need to be a programmer: copy the
commands exactly. Each step ends with a ✅ **check**; do not continue until it passes.

| Step | What | Time | Needs hardware? |
|---|---|---|---|
| 1 | Try it on your computer | 15 min | no |
| 2 | Get the parts | – | – |
| 3 | Prepare the Raspberry Pi's SD card | 20 min | Pi + SD card |
| 4 | Install the software on the Pi | 30–60 min | Pi |
| 5 | Wire the hardware | 1 hour | everything |
| 6 | Install on site and tune | 1–3 days | everything |
| 7 | Daily use and updates | – | – |

---

## 1. Try it on your computer

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** in the installer.
2. Install **Git** from [git-scm.com](https://git-scm.com/downloads).
3. Open a terminal (Windows: *Command Prompt*; macOS/Linux: *Terminal*) and run:

```bash
git clone https://github.com/mazenelnaghy-code/dog-detection.git
cd dog-detection
python -m venv .venv
```

Activate the environment. Do this every time you open a new terminal:

| Windows | macOS / Linux |
|---|---|
| `.venv\Scripts\activate` | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
pip install --no-deps -e .
python -m dog_repeller --demo
```

✅ **Check:** a video window opens. Children and a cat pass without alarm, then a dog walks up, the
log shows `BUZZER -> beep` and `ULTRASONIC REPELLER -> ON`, and the system returns to idle. Open
**http://127.0.0.1:8000** in your browser to see the dashboard. Press `q` to quit.

Nothing to install at all? Use the
[Colab notebook](https://colab.research.google.com/github/mazenelnaghy-code/dog-detection/blob/main/notebooks/demo_colab.ipynb)
in your browser instead.

## 2. Get the parts

The full list, with advice on choosing each part, is in [HARDWARE.md](HARDWARE.md). In short:
a Raspberry Pi 5 (or 4), a 32 GB micro-SD card, a Pi camera (NoIR for night), a 7" HDMI screen,
a 1-channel relay module, an active buzzer module, a 12 V ultrasonic dog repeller set to ≥ 23 kHz,
a 12 V adapter, the official Pi power supply, a fan, jumper wires and an enclosure.

## 3. Prepare the Raspberry Pi's SD card

1. On your computer, install **Raspberry Pi Imager** from
   [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. Choose your **device** (Pi 4 or Pi 5), the OS **Raspberry Pi OS (64-bit)**, and your SD card.
3. Click **Edit settings** (OS customisation) before writing:
   - hostname: `dogguard`
   - username and password: choose your own (you will need them)
   - Wi-Fi: your network name and password, and your country
   - Services tab: **Enable SSH** (password authentication)
4. Write the card, put it in the Pi, connect the screen and power, and wait about 2 minutes.

✅ **Check:** from your computer, `ssh <your-username>@dogguard.local` logs you in. If you have the
screen, a keyboard and mouse connected, you can also use the Terminal on the Pi's desktop.

## 4. Install the software on the Pi

Connect the camera first if you have it (see [WIRING.md, step 2](WIRING.md#2-camera)), with the
power off. Then, on the Pi:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/mazenelnaghy-code/dog-detection.git ~/dog-detection
cd ~/dog-detection
bash deploy/setup_pi.sh            # or: bash deploy/setup_pi.sh desktop  (video on the HDMI screen)
```

Run it as your normal user, **not** with `sudo`; it asks for your password when needed. It takes
30–60 minutes the first time. At the end it prints your **dashboard link**, for example
`http://192.168.1.50:8000/?token=…`. Save it: the token is the password.

✅ **Check:** open the dashboard link on your phone (same Wi-Fi). You see the live camera and
status **ARMED**. If there is no camera yet, the service restarts every few seconds; that is
expected until step 5.

## 5. Wire the hardware

Follow [WIRING.md](WIRING.md), which has a diagram and seven short steps, each with its own check.
**Unplug all power before touching any wire.**

When done, run the self-test:

```bash
cd ~/dog-detection
.venv/bin/python tools/hardware_check.py --config config/local.yaml
```

✅ **Check:** every line says **PASS** (answer `y` when you hear the buzzer and the relay click),
and the summary says `ALL GOOD`.

## 6. Install on site and tune

Mount the camera where it will stay, looking at the area dogs come from (a gate, a fence, the
playground entrance). Then follow the [testing guide](TESTING.md), stages 2–3:

1. **Watch only** for a day or more: keep the repeller unplugged or use `hardware.backend: sim`.
2. **Draw the danger zone** on the real view:
   `.venv/bin/python tools/set_zone.py --config config/local.yaml --write`
   (needs the Pi desktop; with SSH only, edit `zone.rect` in `config/local.yaml` by hand).
3. Check the log for missed dogs and false alarms, and adjust.
4. **Arm it** with staff present, after checking the repeller is set to ≥ 23 kHz.

Restart after any settings change: `sudo systemctl restart dog-repeller`.

## 7. Daily use and updates

| I want to… | Do this |
|---|---|
| see what's happening | open the dashboard link on a phone or PC on the same Wi-Fi |
| switch it off temporarily | dashboard → **Disarm** (and **Arm** again later) |
| test the repeller | dashboard → **Test repeller** |
| see the log | `journalctl -u dog-repeller -f` |
| change a setting | edit `config/local.yaml` (it overrides `config/pi.yaml`), then restart |
| update to the newest code | `cd ~/dog-detection && git pull && sudo systemctl restart dog-repeller` |
| check the hardware | `.venv/bin/python tools/hardware_check.py --config config/local.yaml` |

Your settings in `config/local.yaml` (including the dashboard password) are never overwritten by
`git pull`.

**Something wrong?** See the troubleshooting table in the [README](../README.md#troubleshooting), or
open an issue on GitHub with the output of `tools/hardware_check.py`.
