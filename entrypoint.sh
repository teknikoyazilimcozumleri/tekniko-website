#!/bin/sh

# Keep TLS certificate management outside this container.
# Do not generate OpenSSL/self-signed certs in this entrypoint.

# Veritabanının hazır olmasını bekle (Postgres için)
if [ "${DATABASE:-postgres}" = "postgres" ]
then
    echo "Waiting for postgres..."
    while ! nc -z "${SQL_HOST:-db}" "${SQL_PORT:-5432}"; do
      sleep 0.1
    done
    echo "PostgreSQL started"
fi

# Migration'ları yap
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Superuser değişkenleri verilirse superuser oluştur
if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]
then
    echo "from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists():
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME}', '${DJANGO_SUPERUSER_EMAIL}', '${DJANGO_SUPERUSER_PASSWORD}')
    print('Superuser created')" | python manage.py shell
fi

exec "$@"