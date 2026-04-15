#!/bin/bash

set -e

echo "Stopping NexaFi Backend Services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file="logs/${service_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Stopping $service_name (PID: $pid)...${NC}"
            kill "$pid"

            # Wait for process to stop
            local attempts=0
            while kill -0 "$pid" 2>/dev/null && [ $attempts -lt 10 ]; do
                sleep 1
                attempts=$((attempts + 1))
            done

            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${RED}Force killing $service_name...${NC}"
                kill -9 "$pid" 2>/dev/null || true
            fi

            echo -e "${GREEN}$service_name stopped${NC}"
        else
            echo -e "${YELLOW}$service_name was not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}No PID file found for $service_name${NC}"
    fi
}

# Array of services to stop
declare -a services=(
    "api-gateway"
    "notification-service"
    "compliance-service"
    "ai-service"
    "payment-service"
    "ledger-service"
    "user-service"
)

# Stop each service
for service_name in "${services[@]}"; do
    stop_service "$service_name"
done

# Stop any remaining Python processes that might be NexaFi services
echo "Checking for any remaining NexaFi processes..."
pkill -f "nexafi.*main.py" 2>/dev/null || true

# Stop Redis if it was started by our script
if pgrep redis-server >/dev/null; then
    echo -e "${YELLOW}Stopping Redis server...${NC}"
    redis-cli shutdown 2>/dev/null || true
fi

echo -e "${GREEN}All NexaFi services stopped${NC}"

# Clean up log files if requested
if [ "$1" = "--clean-logs" ]; then
    echo "Cleaning up log files..."
    rm -f logs/*.log
    rm -f logs/*.pid
    echo -e "${GREEN}Log files cleaned${NC}"
fi
