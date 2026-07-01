FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Collect static files at build time
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run with entrypoint (auto-migrate + gunicorn)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
