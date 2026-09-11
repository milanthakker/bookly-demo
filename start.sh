#!/bin/bash
set -euo pipefail

# Always operate from the project root, whatever the caller's cwd is.
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

# Create virtual environment if it doesn't exist
if [ ! -x "$PY" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

# Every command below invokes the venv interpreter by path, so the correct
# Python is used whether or not the venv is activated in the caller's shell.
echo "Installing dependencies..."
"$PY" -m pip install -r requirements.txt --quiet

# Seed the database if it doesn't exist
if [ ! -f "bookly.db" ]; then
  echo "Seeding database..."
  "$PY" -m app.seed
fi

# Start the server
echo "Starting Bookly Support Agent at http://localhost:8000"
exec "$PY" -m uvicorn app.main:app --reload
