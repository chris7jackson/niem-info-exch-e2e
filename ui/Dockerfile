# ---- Builder Stage ----
FROM node:20-alpine AS builder

# Build arguments for version metadata
ARG VERSION=unknown
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

WORKDIR /app

# Copy package files
COPY ui/package*.json ./

# Install dependencies with cache mount
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy application code
COPY ui/ .

# Set build-time environment variables
ENV NEXT_PUBLIC_APP_VERSION=${VERSION} \
    NEXT_PUBLIC_GIT_COMMIT=${GIT_COMMIT} \
    NEXT_PUBLIC_BUILD_DATE=${BUILD_DATE}

# Build Next.js with standalone output
RUN npm run build

# ---- Production Stage ----
FROM node:20-alpine AS runner

# Build arguments for labels
ARG VERSION=unknown
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# OCI image labels
LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="NIEM UI" \
      org.opencontainers.image.description="NIEM Information Exchange Web Interface"

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy only necessary files from builder
COPY --from=builder --chown=appuser:appgroup /app/public ./public
COPY --from=builder --chown=appuser:appgroup /app/.next/standalone ./
COPY --from=builder --chown=appuser:appgroup /app/.next/static ./.next/static

# Set runtime environment variables
ENV NEXT_PUBLIC_APP_VERSION=${VERSION} \
    NEXT_PUBLIC_GIT_COMMIT=${GIT_COMMIT} \
    NEXT_PUBLIC_BUILD_DATE=${BUILD_DATE} \
    NODE_ENV=production

USER appuser

EXPOSE 3000

CMD ["node", "server.js"]