#!/bin/bash
set -e # exit on error

echo "Starting NexaFi User Service..."

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Virtual environment not active. Please run 'source venv/bin/activate' first."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copy .env.example to .env and configure it."
fi

python src/main.py
