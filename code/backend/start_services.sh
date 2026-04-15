#!/bin/bash

# Includes new services and improved error handling

set -e

echo "Starting NexaFi Backend Services ..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}Port $port is already in use${NC}"
        return 1
    fi
    return 0
}

# Function to start a service
start_service() {
    local service_name=$1
    local port=$2
    local service_dir=$3

    echo -e "${YELLOW}Starting $service_name on port $port...${NC}"

    if ! check_port $port; then
        echo -e "${RED}Cannot start $service_name - port $port is in use${NC}"
        return 1
    fi

    cd "$service_dir"

    # Install dependencies if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies for $service_name..."
        pip3 install -r requirements.txt >/dev/null 2>&1 || {
            echo -e "${RED}Failed to install dependencies for $service_name${NC}"
            return 1
        }
    fi

    # Set environment variables
    export SERVICE_NAME="$service_name"
    export SERVICE_PORT="$port"
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/../../shared"

    # Start the service in background
    nohup python3 src/main.py > "../logs/${service_name}.log" 2>&1 &
    local pid=$!
    echo $pid > "../logs/${service_name}.pid"

    # Wait a moment and check if service started successfully
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}$service_name started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start $service_name${NC}"
        return 1
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service_name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:$port/api/v1/health" >/dev/null 2>&1; then
            echo -e "${GREEN}$service_name is ready${NC}"
            return 0
        fi

        echo "Attempt $attempt/$max_attempts - waiting for $service_name..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo -e "${RED}$service_name failed to become ready${NC}"
    return 1
}

# Create logs directory
mkdir -p logs

# Install global dependencies
echo "Installing global dependencies..."
pip3 install -r requirements.txt >/dev/null 2>&1 || {
    echo -e "${RED}Failed to install global dependencies${NC}"
    exit 1
}

# Start Redis (if available) for rate limiting and caching
if command -v redis-server >/dev/null 2>&1; then
    if ! pgrep redis-server >/dev/null; then
        echo -e "${YELLOW}Starting Redis server...${NC}"
        redis-server --daemonize yes --port 6379 >/dev/null 2>&1 || {
            echo -e "${YELLOW}Warning: Could not start Redis. Rate limiting and caching will use fallback methods.${NC}"
        }
    else
        echo -e "${GREEN}Redis is already running${NC}"
    fi
else
    echo -e "${YELLOW}Warning: Redis not found. Rate limiting and caching will use fallback methods.${NC}"
fi

# Array of services to start
declare -a services=(
    "user-service:5001"
    "ledger-service:5002"
    "payment-service:5003"
    "ai-service:5004"
    "compliance-service:5005"
    "notification-service:5006"
    "api-gateway:5000"  # Start gateway last
)

# Start each service
failed_services=()
for service_info in "${services[@]}"; do
    IFS=':' read -r service_name port <<< "$service_info"
    service_dir="$service_name"

    if [ -d "$service_dir" ]; then
        if start_service "$service_name" "$port" "$service_dir"; then
            # Wait for service to be ready (except for API gateway)
            if [ "$service_name" != "api-gateway" ]; then
                if ! wait_for_service "$service_name" "$port"; then
                    failed_services+=("$service_name")
                fi
            fi
        else
            failed_services+=("$service_name")
        fi
    else
        echo -e "${YELLOW}Warning: $service_dir directory not found, skipping $service_name${NC}"
    fi
done

# Special handling for API Gateway - wait for it to be ready
if [ -d "api-gateway" ]; then
    echo "Waiting for API Gateway to be ready..."
    if wait_for_service "api-gateway" "5000"; then
        echo -e "${GREEN}API Gateway is ready and routing requests${NC}"
    else
        failed_services+=("api-gateway")
    fi
fi

# Summary
echo ""
echo "=== NexaFi Backend Startup Summary ==="

if [ ${#failed_services[@]} -eq 0 ]; then
    echo -e "${GREEN}All services started successfully!${NC}"
    echo ""
    echo "Service URLs:"
    echo "  API Gateway:         http://localhost:5000"
    echo "  User Service:        http://localhost:5001"
    echo "  Ledger Service:      http://localhost:5002"
    echo "  Payment Service:     http://localhost:5003"
    echo "  AI Service:          http://localhost:5004"
    echo "  Compliance Service:  http://localhost:5005"
    echo "  Notification Service: http://localhost:5006"
    echo ""
    echo "Health Check: curl http://localhost:5000/health"
    echo "Service List: curl http://localhost:5000/api/v1/services"
    echo ""
    echo "Logs are available in the logs/ directory"
    echo "To stop all services, run: ./stop_services.sh"
else
    echo -e "${RED}Some services failed to start:${NC}"
    for service in "${failed_services[@]}"; do
        echo -e "  ${RED}- $service${NC}"
    done
    echo ""
    echo "Check the logs in the logs/ directory for more details"
    exit 1
fi
