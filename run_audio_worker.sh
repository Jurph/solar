#!/bin/bash
# Run the audio_worker in the web container
# This script keeps the audio_worker running in the background

set -e

CONTAINER="solar-web"

echo "Starting audio_worker in $CONTAINER..."
docker-compose exec -d $CONTAINER python mysite/manage.py audio_worker --skip-warmup

echo "Audio worker started in background"
echo "To view logs: docker-compose logs -f web"
echo "To stop: docker-compose exec $CONTAINER pkill -f audio_worker"

