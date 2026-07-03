#!/bin/sh
set -e

echo ">>> Creating data directory..."
mkdir -p /app/data

echo ">>> Running migrations..."
python manage.py migrate --noinput

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo ">>> Creating superuser if not exists..."
python manage.py createsuperuser --noinput 2>/dev/null || true

echo ">>> Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application
