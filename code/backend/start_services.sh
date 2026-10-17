#!/bin/bash

set -e

echo "Starting NexaFi Backend Services ..."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}Port $port is already in use${NC}"
        return 1
    fi
    return 0
}

start_service() {
    local service_name=$1
    local port=$2
    local service_dir=$3

    echo -e "${YELLOW}Starting $service_name on port $port...${NC}"

    if ! check_port $port; then
        echo -e "${RED}Cannot start $service_name - port $port is in use${NC}"
        return 1
    fi

    (
        cd "$service_dir" || exit 1
        export SERVICE_NAME="$service_name"
        export SERVICE_PORT="$port"
        export PORT="$port"
        export PYTHONPATH="${PYTHONPATH}:$(pwd)/../shared"
        nohup python3 src/main.py > "../logs/${service_name}.log" 2>&1 &
        echo $! > "../logs/${service_name}.pid"
    )

    sleep 2
    local pid
    pid="$(cat "logs/${service_name}.pid" 2>/dev/null)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${GREEN}$service_name started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}Failed to start $service_name${NC}"
        echo -e "${RED}--- last lines of logs/${service_name}.log ---${NC}"
        tail -n 15 "logs/${service_name}.log" 2>/dev/null
        return 1
    fi
}

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
    echo -e "${RED}--- last lines of logs/${service_name}.log ---${NC}"
    tail -n 20 "logs/${service_name}.log" 2>/dev/null
    return 1
}

mkdir -p logs

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

export SECRET_KEY="${SECRET_KEY:-nexafi-local-dev-secret-change-me}"
export DEBUG="${DEBUG:-false}"
mkdir -p /tmp/nexafi-data
export DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/nexafi-data/nexafi.db}"

export USER_SERVICE_URL="${USER_SERVICE_URL:-http://localhost:5001}"
export LEDGER_SERVICE_URL="${LEDGER_SERVICE_URL:-http://localhost:5002}"
export PAYMENT_SERVICE_URL="${PAYMENT_SERVICE_URL:-http://localhost:5003}"
export AI_SERVICE_URL="${AI_SERVICE_URL:-http://localhost:5004}"
export COMPLIANCE_SERVICE_URL="${COMPLIANCE_SERVICE_URL:-http://localhost:5005}"
export NOTIFICATION_SERVICE_URL="${NOTIFICATION_SERVICE_URL:-http://localhost:5007}"

declare -a services=(
    "user-service:5001"
    "auth-service:5011"
    "ledger-service:5002"
    "payment-service:5003"
    "ai-service:5004"
    "compliance-service:5005"
    "document-service:5006"
    "notification-service:5007"
    "credit-service:5008"
    "open-banking-gateway:5010"
    "api-gateway:5000"  # Start gateway last
)

failed_services=()
for service_info in "${services[@]}"; do
    IFS=':' read -r service_name port <<< "$service_info"
    service_dir="$service_name"

    if [ -d "$service_dir" ]; then
        if start_service "$service_name" "$port" "$service_dir"; then
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

if [ -d "api-gateway" ]; then
    echo "Waiting for API Gateway to be ready..."
    if wait_for_service "api-gateway" "5000"; then
        echo -e "${GREEN}API Gateway is ready and routing requests${NC}"
    else
        failed_services+=("api-gateway")
    fi
fi

echo ""
echo "=== NexaFi Backend Startup Summary ==="

if [ ${#failed_services[@]} -eq 0 ]; then
    echo -e "${GREEN}All services started successfully!${NC}"
    echo ""
    echo "Service URLs:"
    echo "  API Gateway:         http://localhost:5000"
    echo "  User Service:        http://localhost:5001"
    echo "  Auth Service:        http://localhost:5011"
    echo "  Ledger Service:      http://localhost:5002"
    echo "  Payment Service:     http://localhost:5003"
    echo "  AI Service:          http://localhost:5004"
    echo "  Compliance Service:  http://localhost:5005"
    echo "  Document Service:    http://localhost:5006"
    echo "  Notification Service: http://localhost:5007"
    echo "  Credit Service:      http://localhost:5008"
    echo "  Open Banking Gateway: http://localhost:5010"
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
