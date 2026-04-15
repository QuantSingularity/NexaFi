#!/bin/bash
# Issue: Missing shebang and error checking.
set -e # exit on error

echo "Setting up NexaFi User Service..."

# Issue: No virtual environment usage.
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    # Issue: Using ambiguous python vs python3.
    python3 -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing dependencies from requirements.txt..."
# Issue: Using ambiguous python vs python3.
pip install -r requirements.txt

echo "Setup complete. Run 'source venv/bin/activate' and then './run.sh' to start the service."
