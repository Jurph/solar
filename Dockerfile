# Solar - Space Traffic Control Simulation Container
# Multi-stage build for Python 3.10 + Django

FROM python:3.10-slim

# Metadata labels
LABEL maintainer="Solar Team"
LABEL description="Solar - Space Traffic Control Simulation"
LABEL version="1.0.0"

# Prevent Python warnings
ENV PYTHONWARNINGS="ignore::DeprecationWarning"

# Set working directory
WORKDIR /app

# Install system dependencies (for TTS/LLM optional runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools and compilers for optional packages
    build-essential git libsndfile1-dev pkg-config \
    # CA certificates for API calls
    ca-certificates \
    # Clean up package manager
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd solar --gid 1000 && useradd solar --gid 1000 --uid 1000 --shell /bin/bash

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create necessary directories for mounts (if they don't exist in codebase)
RUN mkdir -p mysite/templates mysite/wordlists /app/data

# Set ownership (must be done before switching to non-root user)
RUN chown -R solar:solar /app

# Switch to non-root user
USER solar

# Expose Django port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/simulation/health/')" || exit 1

# Run entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
