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

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files only
COPY api/pyproject.toml api/uv.lock ./

# Install dependencies WITHOUT the project itself (for better caching)
# This layer is only invalidated when dependencies change, not on code changes
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY api/src/ ./src/
COPY api/config/ ./config/

# Install the project itself (fast, no dependency downloads)
RUN uv sync --frozen --no-dev

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Create data directories with correct ownership
RUN mkdir -p /data/senzing && chown -R appuser:appgroup /data

# Copy third-party tools (embedded in api directory) and set ownership
COPY --chown=appuser:appgroup api/third_party/niem-ndr /app/third_party/niem-ndr
COPY --chown=appuser:appgroup api/third_party/niem-cmf /app/third_party/niem-cmf
COPY --chown=appuser:appgroup api/third_party/niem-scheval /app/third_party/niem-scheval
COPY --chown=appuser:appgroup api/third_party/niem-tran /app/third_party/niem-tran

# Fix line endings and permissions for all shell scripts
RUN apt-get update && apt-get install -y dos2unix \
    && dos2unix /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool \
    && dos2unix /app/third_party/niem-scheval/scheval-1.0/bin/scheval \
    && dos2unix /app/third_party/niem-tran/niemtran-1.0/bin/niemtran \
    && chmod +x /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool \
    && chmod +x /app/third_party/niem-scheval/scheval-1.0/bin/scheval \
    && chmod +x /app/third_party/niem-tran/niemtran-1.0/bin/niemtran \
    && find /app/third_party/niem-ndr -name "*.sh" -exec chmod +x {} \; \
    && chown -R appuser:appgroup /app/src

USER appuser

EXPOSE ${API_PORT:-8000}

CMD ["sh", "-c", "uv run uvicorn src.niem_api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]