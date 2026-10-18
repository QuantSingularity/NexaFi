FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/code

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 1001 appuser && mkdir -p /data && chown appuser /data

COPY ml_services/ai-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/shared/ /app/code/backend/shared/
COPY ml_services/ai_models/ /app/code/ml_services/ai_models/
COPY ml_services/ai-service/src/ /app/code/ml_services/ai-service/src/

ENV PORT=5004 AI_DB_PATH=/data/ai.db AI_MODEL_DIR=/data/models PYTHONPATH=/app/code/ml_services:/app/code/backend/shared:/app/code/ml_services/ai-service/src
WORKDIR /app/code/ml_services/ai-service/src
USER appuser
VOLUME ["/data"]
EXPOSE 5004

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD curl -fs http://localhost:${PORT}/api/v1/health || exit 1

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --access-logfile - --error-logfile - main:app"]
