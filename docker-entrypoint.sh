#!/bin/bash
# Docker entrypoint script for Solar web service

set -e

echo "Starting Solar web service..."

# Run migrations
echo "Running database migrations..."
python mysite/manage.py migrate

# Start Django development server
echo "Starting Django development server on 0.0.0.0:8000..."
exec python mysite/manage.py runserver 0.0.0.0:8000

