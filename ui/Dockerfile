FROM node:20-alpine

# Build arguments for version metadata
ARG VERSION=unknown
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# Set environment variables for runtime access
ENV NEXT_PUBLIC_APP_VERSION=${VERSION} \
    NEXT_PUBLIC_GIT_COMMIT=${GIT_COMMIT} \
    NEXT_PUBLIC_BUILD_DATE=${BUILD_DATE}

# OCI image labels
LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="NIEM UI" \
      org.opencontainers.image.description="NIEM Information Exchange Web Interface"

WORKDIR /app

# Copy package files
COPY ui/package*.json ./

# Install dependencies
RUN --mount=type=cache,target=/root/.npm \
    npm install

# Copy application code
COPY ui/ .

# Build the application
RUN npm run build

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Change ownership of app directory
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 3000

CMD ["npm", "start"]