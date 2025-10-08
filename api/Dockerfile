FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Java for CMF tool and dos2unix for Windows compatibility
RUN apt-get update && apt-get install -y \
    curl \
    openjdk-21-jre-headless \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Create data directory and third_party directory for volume mounts
RUN mkdir -p /data /app/third_party && \
    chown appuser:appgroup /data && \
    chown -R appuser:appgroup /app/src /app/third_party

# Create entrypoint script to fix permissions on mounted volumes (Windows compatibility)
RUN echo '#!/bin/sh\n\
# Fix line endings and execute permissions on CMF tool if mounted (Windows fix)\n\
if [ -f /app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool ]; then\n\
    # Convert CRLF to LF (Windows line ending fix)\n\
    dos2unix /app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool 2>/dev/null || true\n\
    # Set execute permissions\n\
    chmod +x /app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool 2>/dev/null || true\n\
fi\n\
# Switch to appuser and execute command\n\
exec gosu appuser "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Install gosu for safe user switching in entrypoint (Windows volume permission fix)
RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/*

EXPOSE ${API_PORT:-8000}

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn src.niem_api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]