FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     gcc     && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/

COPY compliance-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY compliance-service/src/ /app/src/

ENV PYTHONPATH=/app:/app/src:/app/shared
ENV FLASK_APP=src/main.py
ENV PORT=5005

WORKDIR /app/src

EXPOSE 5005

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --access-logfile - --error-logfile - main:app"]
