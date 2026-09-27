#!/bin/sh
set -e

echo "==> Starting Hackathon Auth Backend Service..."

# Wait for PostgreSQL if configured
if [ -n "$DB_HOST" ]; then
  echo "==> Checking database connection at $DB_HOST:$DB_PORT..."
  while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
    echo "==> Waiting for PostgreSQL to be ready..."
    sleep 1
  done
  echo "==> PostgreSQL is ready!"
fi

echo "==> Making migrations..."
python manage.py makemigrations users --noinput

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Ensuring cache table (used by API rate limiting) exists..."
python manage.py createcachetable

# Auto-create superuser if credentials provided
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "==> Ensuring admin superuser exists..."
  python - <<END
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@hackathon.local')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password, role=User.Role.ADMIN)
    print(f"==> Superuser '{username}' created successfully with ADMIN role.")
else:
    print(f"==> Superuser '{username}' already exists.")
END
fi

echo "==> Starting server: $@"
exec "$@"
