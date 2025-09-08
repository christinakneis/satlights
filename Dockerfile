FROM python:3.13-slim

# Keep python output unbuffered; make src importable
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Create app dir
WORKDIR /app

# Install runtime deps first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy source and example config
COPY src/ /app/src/
COPY config.example.yaml /app/config.example.yaml

# Create a non-root user (UID 10001) and ensure permissions
RUN useradd -u 10001 -m appuser && \
    mkdir -p /out && chown -R 10001:10001 /app /out

USER 10001

# Default ENTRYPOINT runs the CLI; container expects /app/config.yaml to be mounted
ENTRYPOINT ["python", "-m", "satlight.cli", "--config", "/app/config.yaml"]
