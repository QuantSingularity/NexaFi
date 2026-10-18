FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     gcc     && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/

COPY api-gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api-gateway/src/ /app/src/

ENV PYTHONPATH=/app:/app/src:/app/shared
ENV FLASK_APP=src/main.py
ENV PORT=5000

WORKDIR /app/src

EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --access-logfile - --error-logfile - main:app"]
