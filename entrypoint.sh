#!/bin/sh
set -eu

CACHE_DIR=/app/cache

echo "Starting StoryGrabber entrypoint script..."

# If running as root, ensure the cache directory exists and is writable by appuser
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$CACHE_DIR"
  chown -R appuser:appuser "$CACHE_DIR" || true
  exec su appuser -s /bin/sh -c 'GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120} exec poetry run gunicorn -w 4 --bind 0.0.0.0:80 --timeout "$GUNICORN_TIMEOUT" "storygrabber:create_app()"'
else
  # Already running as non-root
  exec sh -c 'GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120} exec poetry run gunicorn -w 4 --bind 0.0.0.0:80 --timeout "$GUNICORN_TIMEOUT" "storygrabber:create_app()"'
fi

