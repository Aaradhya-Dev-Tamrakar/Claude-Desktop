FROM python:3.11-slim

WORKDIR /app

# Install build essentials for ARM64 / SQLite optimizations
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server application and root templates/prompts
COPY server/ ./server/
COPY sku-templates/ ./sku-templates/
COPY worker-prompts/ ./worker-prompts/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
