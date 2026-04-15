#!/bin/bash
# NexaFi Backend Startup Script

echo "Starting NexaFi Backend Services..."

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/shared"
export SECRET_KEY="${SECRET_KEY:-nexafi-default-secret-key-2024}"

# Check Python version
python3 --version

# Install dependencies if needed
if [ "$1" == "--install" ]; then
    echo "Installing dependencies..."
    pip install -q --no-input -r requirements.txt
fi

# Start services in order
echo "Starting API Gateway on port 5000..."
cd api-gateway/src && python3 main.py &
GATEWAY_PID=$!

echo "Services started. Gateway PID: $GATEWAY_PID"
echo ""
echo "API Gateway: http://localhost:5000"
echo "Health Check: http://localhost:5000/health"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
wait $GATEWAY_PID
