FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Java for CMF tool
RUN apt-get update && apt-get install -y \
    curl \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy third-party tools (embedded in api directory) and set ownership
COPY --chown=appuser:appgroup third_party/niem-ndr /app/third_party/niem-ndr
COPY --chown=appuser:appgroup third_party/niem-cmf /app/third_party/niem-cmf

# Create data directory and fix permissions
RUN mkdir -p /data && chown appuser:appgroup /data
RUN chown -R appuser:appgroup /app/src

USER appuser

EXPOSE ${API_PORT:-8000}

CMD uvicorn src.niem_api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}