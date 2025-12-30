#!/usr/bin/env bash
set -e

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Defaults (in case env vars are not set)
APP_ENV=${APP_ENV:-development}
DB_PATH=${DB_PATH:-./data/app.db}
DATA_ROOT=${DATA_ROOT:-./data/raw}
API_HOST=${API_HOST:-0.0.0.0}
API_PORT=${API_PORT:-8000}

echo "Starting Source.ag assignment app"
echo "Environment : $APP_ENV"
echo "DB path     : $DB_PATH"
echo "Data root   : $DATA_ROOT"
echo "API         : http://$API_HOST:$API_PORT"

# Ensure directories exist
mkdir -p "$(dirname "$DB_PATH")"
mkdir -p "$DATA_ROOT"

# Start FastAPI
uvicorn src.api.main:app \
  --host "$API_HOST" \
  --port "$API_PORT" \
  --reload
