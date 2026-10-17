FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/code

RUN apt-get update && apt-get install -y --no-install-recommends curl gcc && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 1001 appuser

COPY ml_services/analytics-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/shared/ /app/code/backend/shared/
COPY ml_services/analytics-service/src/ /app/code/ml_services/analytics-service/src/
RUN mkdir -p /app/code/ml_services/analytics-service/src/database && chown -R appuser /app/code/ml_services/analytics-service/src/database

ENV PORT=5009
WORKDIR /app/code/ml_services/analytics-service/src
USER appuser
EXPOSE 5009

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD curl -fs http://localhost:${PORT}/api/v1/health || exit 1

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --access-logfile - --error-logfile - main:app"]
