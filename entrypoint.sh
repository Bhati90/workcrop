#!/bin/bash

# Exit on error
set -e

echo "Waiting for database..."
# Use environment variables with defaults
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}

while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "Database started"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files (skip if using S3)
if [ "$USE_S3" != "true" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

# Create superuser if it doesn't exist
echo "Creating superuser if needed..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created.')
else:
    print('Superuser already exists.')
END

# Start server
echo "Starting server..."
exec "$@"