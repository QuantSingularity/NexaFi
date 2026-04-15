#!/bin/bash
# Issue: Missing shebang and error checking.
set -e # exit on error

echo "Starting NexaFi User Service..."

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Virtual environment not active. Please run 'source venv/bin/activate' first."
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copy .env.example to .env and configure it."
fi

# Issue: Using ambiguous python vs python3.
# Run the application using the python interpreter from the active virtual environment
python src/main.py
