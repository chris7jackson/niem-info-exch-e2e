#!/bin/bash
# View only SENZING_DEBUG logs from the API container
# Usage: ./view_senzing_debug.sh

echo "=========================================="
echo "Watching Senzing Debug Logs"
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

docker compose logs api -f 2>&1 | grep --line-buffered "SENZING_DEBUG"
