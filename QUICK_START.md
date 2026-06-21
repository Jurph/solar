# Quick Start: Build & Launch Solar Using Docker Containers

## Prerequisites

- Docker and Docker Compose installed
- (Optional) Ollama running on host machine for LLM

## Step 1: Prepare Environment

```bash
cd solar
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Django
DJANGO_DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# LLM (external, on host machine)
LLM_ENDPOINT=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:1.5b

# TTS (internal Docker service)
TTS_DEVICE=cuda  # or 'cpu' if no GPU
TTS_ENDPOINT=http://tts:8001/v1/audio
```

## Step 2: Build Containers

```bash
# Build both web and TTS containers
docker-compose build

# Or build specific container
docker-compose build web
docker-compose build tts
```

## Step 3: Start Services

```bash
# Start all services in background
docker-compose up -d

# Or start with logs visible
docker-compose up
```

This starts:
- **solar-web** (Django) on port 8000
- **solar-tts** (Chatterbox-TTS) on port 8001
- **solar-audio-worker** (Background audio generation)

## Step 4: Verify Services

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f web
docker-compose logs -f tts
docker-compose logs -f audio-worker

# Test web service
curl http://localhost:8000/api/simulation/health/

# Test TTS service
curl http://localhost:8001/health
```

## Step 5: Access Application

Open in browser:
- **Universe browser**: http://localhost:8000/universe/
- **Event scroller**: http://localhost:8000/events/
- **Admin panel**: http://localhost:8000/admin/
- **TTS health**: http://localhost:8001/health

## Common Commands

```bash
# View logs
docker-compose logs -f web          # Web server
docker-compose logs -f tts          # TTS service
docker-compose logs -f audio-worker # Audio generation

# Manage services
docker-compose stop                 # Stop all services
docker-compose restart              # Restart all services
docker-compose down                 # Stop and remove containers
docker-compose down -v              # Also remove volumes (deletes database)

# Execute commands in container
docker-compose exec web python mysite/manage.py migrate
docker-compose exec web python mysite/manage.py createsuperuser

# View status
docker-compose ps
```

## Troubleshooting

### TTS won't start
```bash
# Check TTS logs
docker-compose logs tts

# Try CPU mode if GPU fails
TTS_DEVICE=cpu docker-compose up -d tts

# Wait for model download (1-2 minutes on first run)
docker-compose logs -f tts
```

### Web can't reach TTS
```bash
# Verify TTS is running
docker-compose ps

# Test connectivity from web container
docker-compose exec web curl http://tts:8001/health
```

### Port already in use
```bash
# Find what's using the port
lsof -i :8000
lsof -i :8001

# Change ports in docker-compose.yml
# ports:
#   - "8080:8000"  # Web on 8080
#   - "8081:8001"  # TTS on 8081
```

### Database errors
```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

## Performance Tips

### GPU Acceleration (Recommended)
```bash
TTS_DEVICE=cuda docker-compose up -d
```

Requires NVIDIA GPU and nvidia-docker.

### CPU Mode (Slower)
```bash
TTS_DEVICE=cpu docker-compose up -d
```

### Model Caching
Model cache persists in `tts-models` volume. First run downloads ~2GB.

To clear cache:
```bash
docker volume rm tts-models
```

## External Services

### Ollama (LLM)

Run on **host machine** (not in Docker):

```bash
# Install Ollama
# https://ollama.ai

# Pull model
ollama pull qwen2.5:1.5b

# Start server
ollama serve
```

Web container connects via `http://host.docker.internal:11434/v1`.

## Full Documentation

See `docs/Docker_SETUP.md` for complete documentation.

