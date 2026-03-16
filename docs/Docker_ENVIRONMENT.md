# Environment Variables Reference

This document lists all environment variables for the Solar Docker container.

## Core Configuration

### DJANGO_DEBUG
- **Type**: `boolean` (string: "True"/"False")
- **Default**: `"True"`
- **Description**: Enable Django debug mode. Set to `False` in production.

### SECRET_KEY
- **Type**: `string`
- **Default**: `"django-insecure-change-in-production"`
- **Description**: Django secret key for session/csrf protection. Generate one using `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

### DJANGO_DATABASE_PATH
- **Type**: `string`
- **Default**: `"/app/db.sqlite3"`
- **Description**: Path to SQLite database file. Mounted from host volume.

## LLM Service Configuration

### LLM_ENDPOINT
- **Type**: `string`
- **Default**: `"http://host.docker.internal:11434/v1"`
- **Description**: URL of OpenAI-compatible LLM endpoint. Use `http://host.docker.internal:11434/v1` for local Ollama.

### LLM_API_KEY
- **Type**: `string`
- **Default**: `""` (empty)
- **Description**: API key if your LLM endpoint requires authentication.

### LLM_MODEL
- **Type**: `string`
- **Default**: `"qwen2.5:1.5b"`
- **Description**: Model name expected by the endpoint. Must match what's available at `LLM_ENDPOINT`.

### LLM_MAX_TOKENS
- **Type**: `integer`
- **Default**: `"500"`
- **Description**: Maximum tokens per LLM response.

## TTS Service Configuration

### TTS_ENDPOINT
- **Type**: `string`
- **Default**: `"http://tts:8001/v1/audio"`
- **Description**: URL of TTS service endpoint. In Docker, use the internal service name `tts:8001`. For local development, use `http://localhost:8001/v1/audio`.

### TTS_API_KEY
- **Type**: `string`
- **Default**: `""` (empty)
- **Description**: API key if TTS endpoint requires authentication.

### TTS_PRE_RENDER_ENABLED
- **Type**: `boolean`
- **Default**: `"False"`
- **Description**: Whether to enable audio pre-rendering. The audio-worker service handles this automatically.

## Simulation Configuration

### UNIVERSE_XML_PATH
- **Type**: `string`
- **Default**: `"xml/milkyway-v005.xml"`
- **Description**: Path to XML universe definition file relative to project root.

### SIMULATION_TIME_SCALE
- **Type**: `integer`
- **Default**: `"1"`
- **Description**: Time multiplier for simulation (1x = real-time, 60x = 60x faster).

### LLM_SAFE_LATENCY_SECONDS
- **Type**: `float`
- **Default**: `"3.0"`
- **Description**: Latency budget for LLM prefetch scheduling in seconds.

## Testing Configuration

### SOLAR_USE_REAL_LLM
- **Type**: `boolean`
- **Default**: `"0"`
- **Description**: Set to `"1"` to enable real LLM calls during tests. Tests use mocks by default.

### SOLAR_LLM_BENCH_DISABLE
- **Type**: `boolean`
- **Default**: `"0"`
- **Description**: Set to `"1"` to disable LLM benchmark logging in tests.

### SOLAR_MIN_FREE_VRAM_MB
- **Type**: `integer`
- **Default**: `"9500"`
- **Description**: Minimum free VRAM (MB) required for @slow tests. Only relevant when GPU is available.

## Production Deployment

For production, set these additional variables:

```bash
DJANGO_DEBUG=False
SECRET_KEY=<generate-a-new-key>
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Example .env File

```bash
# Core
DJANGO_DEBUG=False
SECRET_KEY=<your-generated-secret-key>

# LLM (local Ollama on host machine)
LLM_ENDPOINT=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:1.5b
LLM_MAX_TOKENS=500

# TTS (Docker service)
TTS_ENDPOINT=http://tts:8001/v1/audio
TTS_PRE_RENDER_ENABLED=False

# Simulation
UNIVERSE_XML_PATH=xml/milkyway-v005.xml
SIMULATION_TIME_SCALE=1
LLM_SAFE_LATENCY_SECONDS=3.0
```
