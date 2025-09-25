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

# Create data directory
RUN mkdir -p /data && chown appuser:appgroup /data

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.niem_api.main:app", "--host", "0.0.0.0", "--port", "8000"]