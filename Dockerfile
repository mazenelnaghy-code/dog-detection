# Run the dog repeller demo (or your own video) anywhere Docker runs - no Pi needed.
#   docker build -t dog-repeller .
#   docker run --rm -p 8000:8000 dog-repeller                  # demo -> http://localhost:8000
#   docker run --rm -p 8000:8000 -v "$PWD/videos:/videos" dog-repeller \
#       --source /videos/my.mp4 --sim --no-window --set camera.realtime=true --set dashboard.host=0.0.0.0
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# CPU-only PyTorch keeps the image ~2 GB smaller than the default CUDA build.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps -e . \
    && python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

EXPOSE 8000
ENTRYPOINT ["python", "-m", "dog_repeller"]
CMD ["--demo", "--no-window", "--set", "dashboard.host=0.0.0.0"]
