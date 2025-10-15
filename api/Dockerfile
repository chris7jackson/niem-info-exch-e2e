FROM python:3.12-slim

# Build arguments for version metadata
ARG VERSION=unknown
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# Set environment variables for runtime access
ENV APP_VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE}

# OCI image labels
LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="NIEM API" \
      org.opencontainers.image.description="NIEM Information Exchange API"

WORKDIR /app

# Install system dependencies including Java for CMF tool
RUN apt-get update && apt-get install -y \
    curl \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/src/ ./src/

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy third-party tools (embedded in api directory) and set ownership
COPY --chown=appuser:appgroup api/third_party/niem-ndr /app/third_party/niem-ndr
COPY --chown=appuser:appgroup api/third_party/niem-cmf /app/third_party/niem-cmf

# Create data directory and fix permissions
RUN mkdir -p /data && chown appuser:appgroup /data
RUN chown -R appuser:appgroup /app/src

USER appuser

EXPOSE ${API_PORT:-8000}

CMD uvicorn src.niem_api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}