#!/usr/bin/env bash
# One-time setup on Raspberry Pi OS (64-bit, Bookworm or newer) - Raspberry Pi 4 or 5.
#
#   git clone <your-repo-url> ~/dog-detection
#   cd ~/dog-detection
#   bash deploy/setup_pi.sh            # auto-start in the background (headless + web dashboard)
#   bash deploy/setup_pi.sh desktop    # auto-start with the video on the HDMI screen
#   bash deploy/setup_pi.sh none       # install only, start manually
set -euo pipefail

MODE="${1:-service}"
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    echo "Run this script WITHOUT sudo (it asks for sudo itself when needed):"
    echo "    bash deploy/setup_pi.sh $MODE"
    exit 1
fi
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
RUN_USER="${SUDO_USER:-${USER:-$(id -un)}}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "1/6 System packages (camera, GPIO, OpenCV runtime libraries)"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-picamera2 python3-gpiozero \
    python3-lgpio libgl1 rpicam-apps || sudo apt-get install -y python3-venv python3-pip \
    python3-picamera2 python3-gpiozero python3-lgpio libgl1

step "2/6 Python virtual environment"
# --system-site-packages lets the venv use picamera2 / gpiozero / lgpio installed by apt.
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
# picamera2 is compiled against the system NumPy; keep that exact version to avoid
# "numpy.dtype size changed" errors.
SYS_NUMPY="$(python3 -c 'import numpy; print(numpy.__version__)' 2>/dev/null || true)"
CONSTRAINT="$(mktemp)"
[ -n "$SYS_NUMPY" ] && echo "numpy==$SYS_NUMPY" > "$CONSTRAINT"
.venv/bin/pip install -r requirements-pi.txt -c "$CONSTRAINT" \
    || .venv/bin/pip install -r requirements-pi.txt
.venv/bin/pip install --no-deps -e .
rm -f "$CONSTRAINT"
.venv/bin/python -c "import cv2, picamera2, gpiozero, ultralytics; print('imports OK')"

step "3/6 Camera check"
if command -v rpicam-hello >/dev/null; then
    rpicam-hello --list-cameras || echo "WARNING: no camera detected - check the ribbon cable"
fi

step "4/6 Model: download YOLO11n and export it to NCNN (fastest on the Pi)"
if [ ! -d models/yolo11n_ncnn_model ]; then
    .venv/bin/python training/export.py --weights yolo11n.pt --format ncnn --imgsz 640 --out models
fi

step "5/6 Local config (git-ignored) with a random dashboard password"
if [ ! -f config/local.yaml ]; then
    TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
    cat > config/local.yaml <<YAML
# Your Pi's own settings (not committed to git). Inherits config/pi.yaml.
base: pi.yaml

dashboard:
  token: "$TOKEN"
YAML
fi
TOKEN="$(sed -n 's/^  token: "\(.*\)"/\1/p' config/local.yaml)"

step "6/6 Auto-start ($MODE)"
render() { sed -e "s#__ROOT__#$ROOT#g" -e "s#__USER__#$RUN_USER#g" "$1"; }
case "$MODE" in
    service)
        render deploy/dog-repeller.service | sudo tee /etc/systemd/system/dog-repeller.service >/dev/null
        sudo systemctl daemon-reload
        sudo systemctl enable --now dog-repeller.service
        echo "Logs: journalctl -u dog-repeller -f"
        ;;
    desktop)
        mkdir -p "$HOME/.config/autostart"
        render deploy/dog-repeller.desktop > "$HOME/.config/autostart/dog-repeller.desktop"
        echo "The system will start on the HDMI screen after the next reboot."
        ;;
    none) echo "Start manually: .venv/bin/python -m dog_repeller --config config/local.yaml" ;;
    *) echo "Unknown mode '$MODE' (use service | desktop | none)"; exit 1 ;;
esac

IP="$(hostname -I | awk '{print $1}')"
printf '\n\033[1;32mDone!\033[0m Dashboard: http://%s:8000/?token=%s\n' "$IP" "$TOKEN"
