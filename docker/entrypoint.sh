#!/bin/sh
# Container start-up: apply database migrations, then run the command (gunicorn by default).
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
