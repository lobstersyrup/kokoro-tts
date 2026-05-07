#!/usr/bin/env python3
"""
Kokoro TTS FastAPI Server

OpenAI-compatible Text-to-Speech API server using Kokoro.
All Kokoro voices are available. Single-file, local inference -- no external API calls.
"""
import asyncio
import io
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import numpy as np
import psutil
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from kokoro import KModel, KPipeline
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# API Key Auth (optional, enabled via KOKORO_API_KEY env var)
# ---------------------------------------------------------------------------
_API_KEY = os.getenv("KOKORO_API_KEY", "")
_AUTH_ENABLED = bool(_API_KEY)

# ---------------------------------------------------------------------------
# Server Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------
_HOST = os.getenv("KOKORO_HOST", "0.0.0.0")
_PORT = int(os.getenv("KOKORO_PORT", "8880"))
_MAX_CONCURRENT = int(os.getenv("KOKORO_MAX_CONCURRENT", "4"))
_DEFAULT_VOICE = os.getenv("KOKORO_DEFAULT_VOICE", "af_heart")
_DEFAULT_MODEL = os.getenv("KOKORO_DEFAULT_MODEL", "tts-1")


def _check_api_key(request: Request) -> None:
    """Reject with 401 if KOKORO_API_KEY is set and request has no valid key."""
    if not _AUTH_ENABLED:
        return
    auth_header = request.headers.get("Authorization", "")
    key_header = request.headers.get("X-API-Key", "")
    provided = ""
    if auth_header.startswith("Bearer "):
        provided = auth_header[7:]
    elif auth_header:
        provided = auth_header
    elif key_header:
        provided = key_header
    if not provided or provided != _API_KEY:
        raise HTTPException(401, "Invalid or missing API key")


# All available Kokoro voices (from hexgrad/Kokoro-82M)
KOKORO_VOICES = [
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex", "em_santa", "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "pf_dora", "pm_alex", "pm_santa",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
]

# Supported output formats and their ffmpeg codec mappings
FORMAT_CODECS = {
    "wav": ("pcm_s16le", "wav"),
    "mp3": ("libmp3lame", "mp3"),
    "ogg": ("libvorbis", "ogg"),
    "m4a": ("aac", "ipod"),
}


def _run_pipeline(pipeline: KPipeline, text: str, voice: str, speed: float) -> bytes:
    """Run inference synchronously (called in thread pool). Returns WAV bytes."""
    audio_chunks = []
    for _chunk, _phonemes, audio in pipeline(text, voice=voice, speed=speed):
        audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("Pipeline returned no audio")

    full_audio = np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]
    buf = io.BytesIO()
    sf.write(buf, full_audio, 24000, format="WAV")
    buf.seek(0)
    return buf.read()


def _convert_audio(wav_bytes: bytes, output_format: str) -> bytes:
    """Convert WAV bytes to the requested format using ffmpeg."""
    if output_format == "wav":
        return wav_bytes

    codec, fmt = FORMAT_CODECS.get(output_format, ("pcm_s16le", "wav"))

    # M4A/AAC must be written to a temp file -- AAC can't be piped to stdout
    with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        args = ["ffmpeg", "-y", "-f", "wav", "-acodec", "pcm_s16le", "-i", "pipe:0", "-acodec", codec]
        if fmt:
            args.extend(["-f", fmt])
        args.append(tmp_path)
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.communicate(input=wav_bytes)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model once at startup. All state lives on app.state -- no globals."""
    app.state.started_at = time.time()
    print(f"Loading Kokoro with {len(KOKORO_VOICES)} voices...")
    app.state.model = KModel().to("cpu")
    app.state.pipeline = KPipeline("a", model=app.state.model)
    app.state.executor = ThreadPoolExecutor(max_workers=_MAX_CONCURRENT)
    app.state.ready = True
    print(f"Kokoro ready! (max {_MAX_CONCURRENT} concurrent)")
    yield
    app.state.ready = False
    app.state.executor.shutdown(wait=False)


app = FastAPI(
    title="Kokoro TTS",
    description="OpenAI-compatible Text-to-Speech API using Kokoro",
    lifespan=lifespan,
)


class SpeechRequest(BaseModel):
    model: str = _DEFAULT_MODEL
    input: str
    voice: str = _DEFAULT_VOICE
    speed: float = 1.0
    response_format: str = "mp3"


@app.post("/v1/audio/speech")
async def generate_speech(request: Request, req: SpeechRequest):
    """
    OpenAI-compatible TTS endpoint.
    The `model` and `voice` fields both accept a Kokoro voice name (e.g. "af_heart").
    Runs inference off the async event loop in a thread pool.
    Supports response_format: wav, mp3, ogg, m4a (converted via ffmpeg).
    """
    _check_api_key(request)
    if not req.input:
        raise HTTPException(400, "input is required")

    # Normalize: use `voice` directly. Only fall back to `model` for OpenAI
    # compat when voice is unset (matches default) AND model is a valid voice.
    # Prevents non-voice model names (like "kokoro") from being used as voices.
    voice = req.voice
    if voice == _DEFAULT_VOICE and req.model != _DEFAULT_MODEL and req.model in KOKORO_VOICES:
        voice = req.model

    output_format = (req.response_format or "mp3").lower()
    if output_format not in FORMAT_CODECS:
        raise HTTPException(
            400,
            f"Unsupported format '{output_format}'. Supported: {', '.join(FORMAT_CODECS.keys())}",
        )

    state = request.app.state
    loop = asyncio.get_running_loop()

    # Inference in thread pool (Kokoro/numpy releases the GIL during compute)
    wav_bytes = await loop.run_in_executor(
        state.executor,
        _run_pipeline,
        state.pipeline,
        req.input,
        voice,
        req.speed,
    )

    # Convert to requested format in executor too
    audio_bytes = await loop.run_in_executor(
        state.executor,
        _convert_audio,
        wav_bytes,
        output_format,
    )

    mime_types = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "m4a": "audio/mp4",
    }
    ext = "mp4" if output_format == "m4a" else output_format

    return Response(
        content=audio_bytes,
        media_type=mime_types[output_format],
        headers={"Content-Disposition": f'attachment; filename="speech.{ext}"'},
    )


@app.get("/v1/models")
async def list_models(request: Request):
    """
    OpenAI-compatible models endpoint.
    Returns all available Kokoro voices as models.
    Each voice can be used as the `voice` parameter in /v1/audio/speech.
    """
    _check_api_key(request)
    return {
        "object": "list",
        "data": [
            {
                "id": voice,
                "object": "model",
                "created": 0,
                "owned_by": "kokoro",
                "description": f"Kokoro TTS voice: {voice}",
            }
            for voice in KOKORO_VOICES
        ],
    }


@app.get("/health")
async def health(request: Request):
    """
    Health check endpoint. Always public -- no auth required.
    Returns model loading state, uptime, memory usage, and server config.
    """
    state = request.app.state
    started_at = getattr(state, "started_at", None)
    uptime = int(time.time() - started_at) if started_at else 0
    process = psutil.Process()
    mem_info = process.memory_info()
    return {
        "status": "ok",
        "state": "ready" if getattr(state, "ready", False) else "loading",
        "model": "kokoro",
        "voices": len(KOKORO_VOICES),
        "formats": list(FORMAT_CODECS.keys()),
        "auth_enabled": _AUTH_ENABLED,
        "uptime_seconds": uptime,
        "memory_rss_mb": mem_info.rss // (1024 * 1024),
    }


if __name__ == "__main__":
    # Run with a single process; the thread pool handles concurrent requests.
    # This is more RAM-efficient than workers=4 (which would load 4 model copies).
    uvicorn.run(app, host=_HOST, port=_PORT, workers=1)
