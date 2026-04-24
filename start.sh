#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt --quiet

# Seed the database if it doesn't exist
if [ ! -f "bookly.db" ]; then
  echo "Seeding database..."
  python3 -m app.seed
fi

# Start the server
echo "Starting Bookly Support Agent at http://localhost:8000"
python3 -m uvicorn app.main:app --reload
