"""
Tests for Kokoro TTS FastAPI Server.

Run with: pytest tests/ -v
"""

# Import from the server module
import sys

sys.path.insert(0, ".")
from kokoro_server import FORMAT_CODECS, KOKORO_VOICES, _convert_audio

# ---------------------------------------------------------------------------
# Unit tests (no server required)
# ---------------------------------------------------------------------------

class TestVoiceList:
    def test_voices_not_empty(self):
        assert len(KOKORO_VOICES) > 0

    def test_voices_are_strings(self):
        assert all(isinstance(v, str) for v in KOKORO_VOICES)

    def test_voices_have_prefixes(self):
        prefixes = {v.split("_")[0] for v in KOKORO_VOICES}
        assert len(prefixes) > 5  # Should have af, am, bf, bm, zf, zm, etc.

    def test_no_duplicate_voices(self):
        assert len(KOKORO_VOICES) == len(set(KOKORO_VOICES))

    def test_known_voices_present(self):
        known = {"af_heart", "af_bella", "am_adam", "bf_alice", "zf_xiaoxiao"}
        assert known.issubset(set(KOKORO_VOICES))


class TestFormatCodecs:
    def test_formats_not_empty(self):
        assert len(FORMAT_CODECS) > 0

    def test_format_keys(self):
        assert set(FORMAT_CODECS.keys()) == {"wav", "mp3", "ogg", "m4a"}

    def test_wav_no_conversion(self):
        # WAV should map to pcm_s16le
        assert FORMAT_CODECS["wav"][0] == "pcm_s16le"

    def test_mp3_uses_libmp3lame(self):
        assert FORMAT_CODECS["mp3"][0] == "libmp3lame"

    def test_ogg_uses_libvorbis(self):
        assert FORMAT_CODECS["ogg"][0] == "libvorbis"

    def test_m4a_uses_aac(self):
        assert FORMAT_CODECS["m4a"][0] == "aac"


class TestAudioConversion:
    def test_convert_wav_returns_same(self):
        # A minimal valid WAV header + data
        wav = (
            b"RIFF" + (56).to_bytes(4, "little") + b"WAVE"
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (24000).to_bytes(4, "little")
            + (48000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (0).to_bytes(4, "little")
        )
        result = _convert_audio(wav, "wav")
        assert result == wav

    def test_convert_mp3_produces_mp3(self):
        wav = (
            b"RIFF" + (56).to_bytes(4, "little") + b"WAVE"
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (24000).to_bytes(4, "little")
            + (48000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (0).to_bytes(4, "little")
        )
        result = _convert_audio(wav, "mp3")
        # MP3 files start with ID3 or ff fb
        assert result[:3] == b"ID3" or result[:2] == b"\xff\xfb"
        assert len(result) > 0

    def test_convert_ogg_produces_ogg(self):
        wav = (
            b"RIFF" + (56).to_bytes(4, "little") + b"WAVE"
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (24000).to_bytes(4, "little")
            + (48000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (0).to_bytes(4, "little")
        )
        result = _convert_audio(wav, "ogg")
        # OGG files start with "OggS"
        assert result[:4] == b"OggS"
        assert len(result) > 0

    def test_convert_m4a_produces_m4a(self):
        with open("tests/fixtures/test.wav", "rb") as f:
            wav = f.read()
        result = _convert_audio(wav, "m4a")
        # M4A files contain 'ftyp' box
        assert result.find(b"ftyp") > 0, "M4A should contain ftyp box"
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Integration tests (require a running server on http://localhost:8880)
# Skip with: pytest -m "not integration"
# ---------------------------------------------------------------------------

import httpx
import pytest

BASE = "http://localhost:8880"
TIMEOUT = 60.0

def _assert_valid_audio(response, expected_status=200):
    """Assert response is valid audio and return response for further checks."""
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text[:200]}"
    )
    ct = response.headers.get("content-type", "")
    assert ct.startswith("audio/"), f"Expected audio/* content-type, got: {ct}"
    assert len(response.content) > 0
    return response


# ---------------------------------------------------------------------------
# Happy path — valid voice + valid model combinations
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_voice_equals_model():
    """voice == model (both valid voices): basic happy path."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "af_heart",
            "input": "Hello world",
            "voice": "af_heart",
            "response_format": "mp3",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_non_default_voice_with_standard_model():
    """voice=af_bella (non-default) with model=tts-1 (standard OpenAI model)."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "tts-1",
            "input": "Hello world",
            "voice": "af_bella",
            "response_format": "mp3",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_default_voice_with_non_voice_model():
    """voice=af_heart (default) with model=kokoro (non-voice, non-standard).
    This was the bug case: model must NOT be used as voice."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "kokoro",
            "input": "Hello world",
            "voice": "af_heart",
            "response_format": "mp3",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_default_voice_with_invalid_model():
    """voice=af_heart (default) with model=tts-1-hd (non-voice, standard OpenAI model).
    model should be ignored; voice should be used as-is."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "tts-1-hd",
            "input": "Hello world",
            "voice": "af_heart",
            "response_format": "mp3",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_model_is_voice_no_voice_param():
    """OpenAI compat: model is a valid voice name, no voice param set.
    Should fall back to using model as the voice."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "af_bella",
            "input": "OpenAI compat test",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_model_is_voice_voice_is_default():
    """model is a different valid voice, voice is default (af_heart).
    voice param should win — use af_heart, not model."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "af_bella",
            "input": "Voice should win",
            "voice": "af_heart",
            "response_format": "mp3",
        })
    _assert_valid_audio(response)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_speech_wav_format():
    """POST /v1/audio/speech with response_format=wav should return audio/wav."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "af_heart",
            "input": "Testing wav output",
            "voice": "af_heart",
            "response_format": "wav",
        })
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert len(response.content) > 0


# ---------------------------------------------------------------------------
# Error cases — when voice is invalid, server should return an error
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_voice_with_valid_model():
    """voice=not_a_real_voice (invalid), model=tts-1 (valid standard model).
    Should fail — unrecognized voice name."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "tts-1",
            "input": "Hello",
            "voice": "not_a_real_voice",
            "response_format": "mp3",
        })
    assert response.status_code >= 400, (
        f"Expected error for invalid voice, got {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_voice_and_invalid_model():
    """Both voice and model are invalid, non-voice strings.
    Should fail — nothing to fall back to."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "not_a_real_voice",
            "input": "Hello",
            "voice": "not_a_real_voice",
            "response_format": "mp3",
        })
    assert response.status_code >= 400, (
        f"Expected error for invalid voice+model, got {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_voice_model_is_valid_voice():
    """voice=invalid, model=af_bella (valid voice). Should fail — voice param is
    checked first and model is not used as fallback when voice is explicitly invalid."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "af_bella",
            "input": "Hello",
            "voice": "not_a_real_voice",
            "response_format": "mp3",
        })
    assert response.status_code >= 400, (
        f"Expected error for invalid voice, got {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_input_returns_400():
    """Empty input string should return 400."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "tts-1",
            "input": "",
            "voice": "af_heart",
        })
    assert response.status_code == 400, (
        f"Expected 400 for empty input, got {response.status_code}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unsupported_format_returns_400():
    """Unsupported response_format should return 400."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.post("/v1/audio/speech", json={
            "model": "tts-1",
            "input": "Hello",
            "voice": "af_heart",
            "response_format": "flac",
        })
    assert response.status_code == 400, (
        f"Expected 400 for unsupported format, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Non-auth endpoints
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health should return 200 with a valid status field."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "ready", "loading")
    if "voices" in data:
        assert data["voices"] > 0
    if "formats" in data:
        assert len(data["formats"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_models_endpoint():
    """GET /v1/models should return a list of all available voices."""
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:
        response = await client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    if "object" in data:
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        voice_ids = {m["id"] for m in data["data"]}
        assert "af_heart" in voice_ids
        assert "am_adam" in voice_ids
