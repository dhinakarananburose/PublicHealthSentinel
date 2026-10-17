#!/bin/sh
set -e

# Run safe idempotent initialization (skips if data already exists)
python /app/scripts/init_container.py

# Execute the container command
exec "$@"
