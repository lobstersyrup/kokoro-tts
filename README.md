# Kokoro TTS FastAPI Server

[![CI](https://github.com/lobstersyrup/kokoro-tts/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lobstersyrup/kokoro-tts/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

OpenAI-compatible Text-to-Speech server powered by [Kokoro](https://github.com/hexgrad/kokoro). Runs entirely on CPU with no external API calls -- drop it into any OpenAI-compatible client as a local TTS backend.

## Features

- **OpenAI-compatible endpoint** -- same request/response format as OpenAI's TTS API
- **54 voices** across 10+ languages and accents
- **Multiple output formats** -- WAV, MP3, OGG, M4A (converted via ffmpeg)
- **Local inference** -- runs entirely on CPU, no external API calls
- **Concurrent request handling** -- semaphore + thread pool for parallel generation
- **Environment-driven config** -- host, port, concurrency, defaults, and auth all via env vars

## Quick Start

```bash
git clone https://github.com/lobstersyrup/kokoro-tts.git
cd kokoro-tts

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install system dependency
sudo apt install ffmpeg

# Install Python dependencies
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Run
python kokoro_server.py
```

The server starts on `http://0.0.0.0:8880`. The Kokoro model (~100MB) is downloaded automatically on first run.

### Usage

```bash
curl -X POST http://localhost:8880/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Hello, this is a test of the Kokoro TTS system.",
    "voice": "af_heart",
    "speed": 1.0,
    "response_format": "mp3"
  }' \
  --output speech.mp3
```

### OpenAI Python Client

```python
from openai import OpenAI

client = OpenAI(
    api_key="not-needed",
    base_url="http://localhost:8880/v1"
)

response = client.audio.speech.create(
    model="tts-1",
    input="Hello from Kokoro!",
    voice="af_heart",
    response_format="mp3"
)
response.stream_to_file("output.mp3")
```

## Configuration

All settings are controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KOKORO_HOST` | `0.0.0.0` | Bind address |
| `KOKORO_PORT` | `8880` | Listen port |
| `KOKORO_MAX_CONCURRENT` | `4` | Max parallel TTS generations |
| `KOKORO_DEFAULT_VOICE` | `af_heart` | Voice used when none specified |
| `KOKORO_DEFAULT_MODEL` | `tts-1` | Model field default (OpenAI compat) |
| `KOKORO_API_KEY` | (empty) | API key for auth; empty = no auth |

### Voice Fallback Logic

The `model` and `voice` fields both accept a Kokoro voice name. The server resolves the active voice like this:

1. If `voice` is set to something other than `KOKORO_DEFAULT_VOICE` → use it
2. Otherwise, if `model` is set to something other than `KOKORO_DEFAULT_MODEL` → use it as the voice
3. Otherwise → use `KOKORO_DEFAULT_VOICE`

This means OpenAI clients sending `model="tts-1", voice="af_heart"` get the default voice, while `model="af_bella"` works as a shorthand for voice selection.

## Deployment

### systemd (Linux)

Create a user service for automatic startup and crash recovery:

```bash
# Create the unit file
cat > ~/.config/systemd/user/kokoro-tts.service << 'EOF'
[Unit]
Description=Kokoro TTS Server
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/path/to/venv/bin/python /path/to/kokoro-tts/kokoro_server.py
Restart=always
RestartSec=5
WorkingDirectory=/path/to/kokoro-tts
Environment=HOME=%h
Environment=PATH=/path/to/venv/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
EOF

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now kokoro-tts

# Verify
systemctl --user status kokoro-tts
curl http://localhost:8880/health
```

To override config, add `Environment=KOKORO_PORT=8881` (or any other variable) to the `[Service]` section and restart.

Pass custom environment variables by adding lines to the `[Service]` block:

```ini
Environment=KOKORO_PORT=8881
Environment=KOKORO_MAX_CONCURRENT=2
Environment=KOKORO_API_KEY=your-secret-key
```

### Docker

```bash
# Build and start with defaults
docker compose up -d

# Or with custom configuration
KOKORO_PORT=8881 KOKORO_MAX_CONCURRENT=2 docker compose up -d

# Check health
curl http://localhost:8880/health
```

The Docker image includes ffmpeg, all Python dependencies, and pre-downloads the Kokoro model so the first request is instant. A named volume (`kokoro-model-cache`) persists the model across container rebuilds.

#### Custom Docker Compose Overrides

Create a `docker-compose.override.yml` for persistent configuration:

```yaml
services:
  kokoro-tts:
    ports:
      - "8881:8881"
    environment:
      - KOKORO_PORT=8881
      - KOKORO_MAX_CONCURRENT=2
      - KOKORO_API_KEY=your-secret-key
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/speech` | POST | Generate speech (OpenAI-compatible) |
| `/v1/models` | GET | List all 54 available voices |
| `/health` | GET | Health check with voice count, formats, uptime |

### Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| `wav` | `.wav` | PCM, no conversion -- fastest |
| `mp3` | `.mp3` | MPEG audio (default) |
| `ogg` | `.ogg` | Ogg Vorbis |
| `m4a` | `.m4a` | AAC in M4A container |

## Voice List

All 54 available voices. Prefix indicates language/accent:

| Prefix | Language/Accent |
|--------|----------------|
| `af_` | American Female |
| `am_` | American Male |
| `bf_` | British Female |
| `bm_` | British Male |
| `ef_` | European Female |
| `em_` | European Male |
| `ff_` | French Female |
| `hf_` | Hindi Female |
| `hm_` | Hindi Male |
| `if_` | Italian Female |
| `im_` | Italian Male |
| `jf_` | Japanese Female |
| `jm_` | Japanese Male |
| `pf_` | Polish Female |
| `pm_` | Polish Male |
| `zf_` | Chinese Female |
| `zm_` | Mandarin Male |

### American Female (`af_`)

| Voice | Description |
|-------|-------------|
| `af_alloy` | Warm, versatile. Good all-rounder |
| `af_aoede` | Soft, melodic with a gentle tone |
| `af_bella` | Bright, warm. Popular choice |
| `af_heart` | Expressive, emotionally rich. Great for engaging content |
| `af_jessica` | Clear, professional |
| `af_kore` | Neutral, balanced |
| `af_nicole` | Soft-spoken, calm |
| `af_nova` | Upbeat, energetic |
| `af_river` | Smooth, flowing with a relaxed cadence |
| `af_sarah` | Neutral, clear |
| `af_sky` | Bright, cheerful |

### American Male (`am_`)

| Voice | Description |
|-------|-------------|
| `am_adam` | Deep, authoritative |
| `am_echo` | Warm, steady with a calm presence |
| `am_eric` | Friendly, conversational |
| `am_fenrir` | Serious, deep |
| `am_liam` | Clear, young |
| `am_michael` | Warm, mature |
| `am_onyx` | Deep, rich |
| `am_puck` | Lighter, youthful |
| `am_santa` | Deep, jolly (character) |

### British Female (`bf_`)

| Voice | Description |
|-------|-------------|
| `bf_alice` | Elegant, refined |
| `bf_emma` | Warm, sophisticated |
| `bf_isabella` | Clear, articulate |
| `bf_lily` | Bright, pleasant |

### British Male (`bm_`)

| Voice | Description |
|-------|-------------|
| `bm_daniel` | Clear, professional |
| `bm_fable` | Expressive, storytelling |
| `bm_george` | Deep, authoritative |
| `bm_lewis` | Warm, friendly |

### European (`ef_` / `em_` / `ff_`)

| Voice | Description |
|-------|-------------|
| `ef_dora` | European female |
| `em_alex` | European male, versatile |
| `em_santa` | European male, deeper tone |
| `ff_siwis` | French Swiss female |

### Hindi (`hf_` / `hm_`)

| Voice | Description |
|-------|-------------|
| `hf_alpha` | Hindi female, clear and precise |
| `hf_beta` | Hindi female, softer tone |
| `hm_omega` | Hindi male, deep |
| `hm_psi` | Hindi male, calm |

### Italian (`if_` / `im_`)

| Voice | Description |
|-------|-------------|
| `if_sara` | Italian female, expressive |
| `im_nicola` | Italian male, warm |

### Japanese (`jf_` / `jm_`)

| Voice | Description |
|-------|-------------|
| `jf_alpha` | Japanese female, clear |
| `jf_gongitsune` | Japanese female, softer |
| `jf_nezumi` | Japanese female, gentle |
| `jf_tebukuro` | Japanese female, warm |
| `jm_kumo` | Japanese male |

### Polish (`pf_` / `pm_`)

| Voice | Description |
|-------|-------------|
| `pf_dora` | Polish female |
| `pm_alex` | Polish male, warm |
| `pm_santa` | Polish male, deeper |

### Chinese Female (`zf_`)

| Voice | Description |
|-------|-------------|
| `zf_xiaobei` | Northern accent |
| `zf_xiaoni` | Youthful |
| `zf_xiaoxiao` | Standard |
| `zf_xiaoyi` | Gentle |

### Mandarin Male (`zm_`)

| Voice | Description |
|-------|-------------|
| `zm_yunjian` | Clear |
| `zm_yunxi` | Expressive |
| `zm_yunxia` | Warm |
| `zm_yunyang` | Deep |

## Architecture

- **FastAPI** -- HTTP endpoints and request validation
- **Uvicorn** -- ASGI server (single worker, async concurrency)
- **Kokoro** -- local TTS inference pipeline
- **Semaphore + ThreadPoolExecutor** -- safe concurrent generation on CPU
- **Soundfile** -- WAV encoding; ffmpeg handles format conversion

The Kokoro pipeline is not thread-safe, so inference runs in a thread pool gated by a semaphore (default 4 concurrent). This avoids OOM while maintaining reasonable throughput. A single Uvicorn worker is used to avoid loading multiple model copies into memory.

## Ports

Default: **8880** (configurable via `KOKORO_PORT`)
