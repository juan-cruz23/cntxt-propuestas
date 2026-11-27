#!/bin/sh
set -e

echo ">>> Creating data and media directories..."
mkdir -p /app/data /app/media

echo ">>> Running migrations..."
python manage.py migrate --noinput

echo ">>> Loading CNTXT services catalog..."
python manage.py cargar_catalogo_cntxt || true

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo ">>> Creating superuser if not exists..."
python manage.py createsuperuser --noinput 2>/dev/null || true

echo ">>> Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 300 config.wsgi:application
