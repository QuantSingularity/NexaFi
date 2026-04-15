#!/bin/bash

echo "🛑 Stopping NexaFi Infrastructure Services..."

# Stop infrastructure services
docker-compose down

echo "🎉 Infrastructure services stopped!"
