#!/bin/bash
# Runs once, the first time the Postgres volume is created.
# Each app gets its own database.
set -euo pipefail

for db in crm tracking; do
  echo "Creating database: $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -c "CREATE DATABASE \"$db\" OWNER \"$POSTGRES_USER\";"
done
