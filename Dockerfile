FROM python:3.12-slim

# System deps for geopandas/pyogrio (GDAL via pyogrio wheels — no apt GDAL needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download real data at build time so it's baked into the image
COPY scripts/download_data.py scripts/download_data.py
RUN python3 scripts/download_data.py

# Copy application code
COPY src/       src/
COPY templates/ templates/
COPY app.py     .

EXPOSE 8080

# --preload: load basins+wells once before forking workers
# 2 workers on a 256 MB VM; each handles one request at a time (GIL fine here)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--preload", \
     "--timeout", "60", "app:app"]
