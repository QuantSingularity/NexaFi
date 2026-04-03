#!/usr/bin/env bash
# NexaFi Infrastructure Startup Script
# Starts local development infrastructure via Docker Compose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}    $1"; }
log_success() { echo -e "${GREEN}[OK]${NC}      $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC}    $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC}   $1"; }

# ── Preflight checks ───────────────────────────────────────────────────────────
check_requirements() {
    log_info "Checking requirements..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed. Visit https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose v2 is required. Update Docker Desktop or install the compose plugin."
        exit 1
    fi

    if [[ ! -f "${ENV_FILE}" ]]; then
        if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
            log_warning ".env not found. Copying from .env.example — please fill in real values before use."
            cp "${SCRIPT_DIR}/.env.example" "${ENV_FILE}"
        else
            log_error ".env file missing. Create one from .env.example."
            exit 1
        fi
    fi

    # Warn about unfilled placeholder values
    if grep -q "change_me" "${ENV_FILE}"; then
        log_warning ".env still contains placeholder values (change_me). Update before production use."
    fi

    log_success "Requirements satisfied"
}

# ── Start services ─────────────────────────────────────────────────────────────
start_services() {
    log_info "Pulling latest images..."
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull \
        redis rabbitmq elasticsearch kibana 2>/dev/null || true

    log_info "Starting infrastructure services..."
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d \
        redis rabbitmq elasticsearch kibana

    log_info "Waiting for infrastructure to become healthy (up to 3 minutes)..."
    local timeout=180
    local elapsed=0
    local interval=5

    while true; do
        local unhealthy
        unhealthy=$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" \
            ps --format json 2>/dev/null \
            | python3 -c "
import sys, json
data = sys.stdin.read().strip()
# docker compose ps --format json emits one JSON object per line
lines = [l for l in data.splitlines() if l.strip()]
unhealthy = [json.loads(l)['Name'] for l in lines
             if json.loads(l).get('Health','') not in ('healthy','')]
print(len(unhealthy))
" 2>/dev/null || echo "0")

        if [[ "${unhealthy}" == "0" ]]; then
            break
        fi

        if [[ ${elapsed} -ge ${timeout} ]]; then
            log_error "Timed out waiting for services to become healthy."
            docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
            exit 1
        fi

        sleep ${interval}
        elapsed=$(( elapsed + interval ))
    done

    log_success "Infrastructure services are healthy"
}

# ── Health checks ──────────────────────────────────────────────────────────────
verify_health() {
    log_info "Verifying service endpoints..."

    # Load env for password variables
    set -a; source "${ENV_FILE}"; set +a

    local all_ok=true

    # Redis
    if docker exec nexafi-redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
        log_success "Redis        → localhost:6379"
    else
        log_error   "Redis        → not responding"
        all_ok=false
    fi

    # RabbitMQ management API
    if curl -sf -u "${RABBITMQ_USER:-nexafi}:${RABBITMQ_PASSWORD}" \
        http://localhost:15672/api/healthchecks/node &>/dev/null; then
        log_success "RabbitMQ     → localhost:5672  (management: localhost:15672)"
    else
        log_error   "RabbitMQ     → not responding"
        all_ok=false
    fi

    # Elasticsearch
    if curl -sf -u "elastic:${ELASTICSEARCH_PASSWORD}" \
        "http://localhost:9200/_cluster/health" &>/dev/null; then
        log_success "Elasticsearch → localhost:9200"
    else
        log_error   "Elasticsearch → not responding"
        all_ok=false
    fi

    # Kibana
    if curl -sf "http://localhost:5601/api/status" &>/dev/null; then
        log_success "Kibana        → localhost:5601"
    else
        log_warning "Kibana        → still starting up (this can take 2–3 min)"
    fi

    if [[ "${all_ok}" != "true" ]]; then
        log_error "One or more services failed. Run: docker compose logs <service>"
        exit 1
    fi
}

# ── Summary ────────────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       NexaFi Infrastructure — Ready                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BLUE}Service         URL${NC}"
    echo    "  ─────────────────────────────────────────────────────"
    echo    "  Redis           localhost:6379"
    echo    "  RabbitMQ AMQP   localhost:5672"
    echo    "  RabbitMQ Mgmt   http://localhost:15672"
    echo    "  Elasticsearch   http://localhost:9200"
    echo    "  Kibana          http://localhost:5601"
    echo ""
    echo    "  To start application services:"
    echo -e "  ${YELLOW}docker compose up -d${NC}"
    echo ""
    echo    "  To view logs:"
    echo -e "  ${YELLOW}docker compose logs -f <service>${NC}"
    echo ""
    echo    "  To stop everything:"
    echo -e "  ${YELLOW}docker compose down${NC}"
    echo ""
}

main() {
    echo ""
    log_info "Starting NexaFi Infrastructure..."
    echo ""
    check_requirements
    start_services
    verify_health
    print_summary
}

main "$@"
