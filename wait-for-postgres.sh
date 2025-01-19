#!/bin/bash
set -e  # Останавливает выполнение при ошибке

host="$1"  # Хост базы данных
shift
cmd="$@"  # Остальные команды

# Ждём, пока Postgres станет доступным
until pg_isready -h "$host" -p 5432; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
