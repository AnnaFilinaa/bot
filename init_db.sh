#!/bin/bash
set -e

# Проверяем, существует ли база данных
psql -U "$POSTGRES_USER" -tc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'" | grep -q 1 || \
psql -U "$POSTGRES_USER" -c "CREATE DATABASE \"$POSTGRES_DB\""
