FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch first (large download, cache separately)
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY kokoro_server.py .

# Pre-download the Kokoro model (~100MB) so first request is instant
RUN python -c "from kokoro import KModel; KModel()" || true

EXPOSE 8880

# All configuration is driven by environment variables (see README)
# KOKORO_HOST         — bind address (default: 0.0.0.0)
# KOKORO_PORT         — listen port (default: 8880)
# KOKORO_MAX_CONCURRENT — max parallel generations (default: 4)
# KOKORO_DEFAULT_VOICE — default voice name (default: af_heart)
# KOKORO_DEFAULT_MODEL — default model name (default: tts-1)
# KOKORO_API_KEY      — API key for auth (empty = no auth)

CMD ["python", "kokoro_server.py"]
