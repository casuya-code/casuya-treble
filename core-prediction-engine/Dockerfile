FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY gateway ./gateway
COPY 0-auth-service ./0-auth-service
COPY 1-data-ingestion-service ./1-data-ingestion-service
COPY 2-poisson-analytics-engine ./2-poisson-analytics-engine
COPY 3-market-odds-monitor ./3-market-odds-monitor
COPY 4-slip-generator-service ./4-slip-generator-service
COPY 5-realtime-tracker-service ./5-realtime-tracker-service
COPY 6-database-purger ./6-database-purger
COPY 7-basketball-filter-service ./7-basketball-filter-service
COPY jobs ./jobs

ENV PYTHONPATH=/app

CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
