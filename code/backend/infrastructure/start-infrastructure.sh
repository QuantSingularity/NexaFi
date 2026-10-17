#!/bin/bash

echo "Starting NexaFi Infrastructure Services..."

docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 30

echo "Checking service health..."

if redis-cli -h localhost -p 6379 ping | grep -q PONG; then
    echo "Redis is running"
else
    echo "Redis is not responding"
fi

if curl -s http://localhost:15672 > /dev/null; then
    echo "RabbitMQ is running"
else
    echo "RabbitMQ is not responding"
fi

if curl -s http://localhost:9200 > /dev/null; then
    echo "Elasticsearch is running"
else
    echo "Elasticsearch is not responding"
fi

if curl -s http://localhost:5601 > /dev/null; then
    echo "Kibana is running"
else
    echo "Kibana is not responding"
fi

echo "Infrastructure setup complete!"
echo "Access Kibana at: http://localhost:5601"
echo "Access RabbitMQ Management at: http://localhost:15672 (nexafi/nexafi123)"
