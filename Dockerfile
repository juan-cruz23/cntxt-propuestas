FROM node:22-slim AS assets

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY tailwind ./tailwind
COPY templates/admin_panel ./templates/admin_panel
RUN npm run build:css

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
COPY --from=assets /app/static/css/app.css ./static/css/app.css

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Collect static files at build time
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run with entrypoint (auto-migrate + gunicorn)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
