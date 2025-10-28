#!/bin/bash

echo "Starting Workcrop application..."

# Run database migrations
echo "Running database migrations..."


# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start gunicorn
echo "Starting gunicorn on port ${PORT:-10000}..."
exec gunicorn crop.wsgi:application \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info