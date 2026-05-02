# Contributing to Kokoro TTS

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/lobstersyrup/kokoro-tts.git
cd kokoro-tts
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (includes test runner)
pip install pytest pytest-asyncio httpx ruff

# Install ffmpeg (for format conversion tests)
sudo apt install ffmpeg
```

## Running Tests

```bash
# All unit tests (no server needed)
pytest tests/test_server.py -v

# Skip integration tests (useful in CI without a running server)
pytest tests/test_server.py -v -m "not integration"

# Individual test groups
pytest tests/test_server.py::TestVoiceList -v
pytest tests/test_server.py::TestFormatCodecs -v
pytest tests/test_server.py::TestAudioConversion -v

# Integration tests (require a running server on http://localhost:8880)
# Start the server first:
#   python kokoro_server.py
# Then run:
pytest tests/test_server.py -v -m integration

# Docker Compose (runs server with healthcheck):
docker compose up -d
pytest tests/test_server.py -v -m integration
docker compose down
```

## Code Style

This project uses `ruff` for linting:

```bash
ruff check .
ruff check . --fix  # auto-fix issues
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and add tests
4. Ensure all tests pass (`pytest tests/test_server.py -v`)
5. Ensure lint passes (`ruff check .`)
6. Submit a pull request with a clear description

## Adding New Voices

The voice list is hardcoded in `kokoro_server.py` as `KOKORO_VOICES`. When Kokoro releases new voices, update that list and add entries to the voice description table in `README.md`.

## Adding New Output Formats

To add a new format (e.g. `flac`):

1. Add the format to `FORMAT_CODECS` dict in `kokoro_server.py`
2. Add tests in `TestAudioConversion`
3. Update README with the new format
