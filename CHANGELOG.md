# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] -- 2026-05-02

### Added
- OpenAI-compatible `/v1/audio/speech` endpoint
- 54 Kokoro voices across 10+ languages
- `/v1/models` endpoint listing all available voices
- `/health` endpoint with status, voice count, and supported formats
- Multiple output format support: WAV, MP3, OGG, M4A (via ffmpeg)
- Concurrent request handling with semaphore + thread pool (max 4 concurrent)
- pytest test suite with unit and integration tests
- systemd service file for Linux deployment
- MIT License

### Technical Details

- Kokoro runs locally on CPU -- no external API calls
- Single-file server (`kokoro_server.py`) with no framework lock-in
- FastAPI + Uvicorn for the HTTP layer
- WAV from Kokoro, converted to requested format via ffmpeg
