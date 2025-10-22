#!/bin/bash
# Development helper script for multi-worktree workflows
# Automatically assigns unique ports based on directory name
# Usage: ./dev.sh [docker compose commands]
# Examples:
#   ./dev.sh up -d
#   ./dev.sh down
#   ./dev.sh logs -f api
#   ./dev.sh ps

set -e

# Get directory name and create hash for unique port offset
DIR_NAME=$(basename "$PWD")

# Create a simple hash from directory name (cross-platform compatible)
# Using cksum for better cross-platform compatibility than md5sum
HASH=$(echo -n "$DIR_NAME" | cksum | cut -d' ' -f1)
PORT_OFFSET=$((HASH % 50))

# Calculate unique ports
export API_PORT=$((8000 + PORT_OFFSET))
export UI_PORT=$((3000 + PORT_OFFSET))
export COMPOSE_PROJECT_NAME="niem-${DIR_NAME}"

# Display configuration
echo "🚀 Starting development environment for: ${DIR_NAME}"
echo "   Project: ${COMPOSE_PROJECT_NAME}"
echo "   API Port: ${API_PORT}"
echo "   UI Port: ${UI_PORT}"
echo ""

# Check if shared infrastructure is running
if docker network inspect niem-infra >/dev/null 2>&1; then
    echo "✓ Using shared infrastructure (niem-infra network)"
else
    echo "⚠️  Shared infrastructure not found."
    echo "   To start shared infrastructure:"
    echo "   docker compose -f docker-compose.infra.yml up -d"
    echo ""
    echo "   Continuing with local infrastructure..."
    echo ""
fi

# Pass all arguments to docker compose
exec docker compose "$@"
