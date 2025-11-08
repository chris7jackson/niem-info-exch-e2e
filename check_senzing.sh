#!/bin/bash
# Quick diagnostic script to check Senzing configuration
# Usage: ./check_senzing.sh

echo "=========================================="
echo "Senzing Configuration Diagnostic"
echo "=========================================="
echo ""

# Check if API is running
echo "1. Checking API availability..."
if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
    echo "   ✅ API is running"
else
    echo "   ❌ API is not running"
    echo "   Run: docker compose up -d api"
    exit 1
fi
echo ""

# Check Senzing health endpoint
echo "2. Checking Senzing components..."
echo ""

HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/entity-resolution/health -H "Authorization: Bearer devtoken")

# Parse response with jq if available, otherwise show raw
if command -v jq &> /dev/null; then
    # Extract component statuses
    SDK_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.components.sdk.status')
    LICENSE_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.license.status')
    LICENSE_VALID=$(echo "$HEALTH_RESPONSE" | jq -r '.license.valid')
    LICENSE_TYPE=$(echo "$HEALTH_RESPONSE" | jq -r '.license.type // "unknown"')
    GRPC_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.components.grpc.status')
    GRPC_URL=$(echo "$HEALTH_RESPONSE" | jq -r '.components.grpc.url')
    DB_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.database.status')
    DB_RECORDS=$(echo "$HEALTH_RESPONSE" | jq -r '.database.record_count')
    DB_ENTITIES=$(echo "$HEALTH_RESPONSE" | jq -r '.database.entity_count')
    NIEM_REGISTERED=$(echo "$HEALTH_RESPONSE" | jq -r '.database.niem_graph_registered // "unknown"')

    # Display component status
    echo "   Component Status:"
    echo "   ┌─────────────────────────────────────────────┐"

    # SDK
    if [ "$SDK_STATUS" = "healthy" ]; then
        echo "   │ ✅ Senzing SDK          : $SDK_STATUS"
    else
        echo "   │ ❌ Senzing SDK          : $SDK_STATUS"
    fi

    # License
    if [ "$LICENSE_STATUS" = "healthy" ] && [ "$LICENSE_VALID" = "true" ]; then
        echo "   │ ✅ License File         : valid ($LICENSE_TYPE)"
    elif [ "$LICENSE_STATUS" = "missing" ]; then
        echo "   │ ❌ License File         : missing"
    else
        echo "   │ ⚠️  License File         : $LICENSE_STATUS"
    fi

    # gRPC Server
    if [ "$GRPC_STATUS" = "healthy" ]; then
        echo "   │ ✅ gRPC Server          : $GRPC_STATUS ($GRPC_URL)"
    else
        echo "   │ ❌ gRPC Server          : $GRPC_STATUS"
    fi

    # PostgreSQL Database
    if [ "$DB_STATUS" = "healthy" ]; then
        echo "   │ ✅ PostgreSQL Database  : $DB_STATUS"
        echo "   │    - Records: $DB_RECORDS, Entities: $DB_ENTITIES"
        if [ "$NIEM_REGISTERED" = "true" ]; then
            echo "   │    - NIEM_GRAPH datasource: ✅ registered"
        else
            echo "   │    - NIEM_GRAPH datasource: ⚠️  not registered"
        fi
    else
        echo "   │ ❌ PostgreSQL Database  : $DB_STATUS"
    fi

    echo "   └─────────────────────────────────────────────┘"

    # Check overall status
    OVERALL_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.overall_status')

    echo ""
    echo "=========================================="
    if [ "$OVERALL_STATUS" = "healthy" ]; then
        echo "✅ Senzing Status: HEALTHY"
        echo "=========================================="
        echo ""
        echo "Your Senzing setup is working correctly!"
        echo ""
        echo "Next steps:"
        echo "  - Run entity resolution from the UI at http://localhost:3000/graph"
        echo "  - Or use the API: POST /api/entity-resolution/run"
        echo "  - View debug logs: ./view_senzing_debug.sh"
    elif [ "$OVERALL_STATUS" = "degraded" ]; then
        echo "⚠️  Senzing Status: DEGRADED"
        echo "=========================================="
        echo ""
        echo "Senzing is partially working but has issues."
        echo "Check the 'errors' array above for details."
    else
        echo "❌ Senzing Status: UNHEALTHY"
        echo "=========================================="
        echo ""
        echo "Senzing is not working correctly."
        echo ""
        echo "Common issues:"
        echo ""

        # Check specific issues
        SDK_INSTALLED=$(echo "$HEALTH_RESPONSE" | jq -r '.senzing_sdk_installed')
        LICENSE_CONFIGURED=$(echo "$HEALTH_RESPONSE" | jq -r '.license_configured')
        CLIENT_INITIALIZED=$(echo "$HEALTH_RESPONSE" | jq -r '.client_initialized')

        if [ "$SDK_INSTALLED" = "false" ]; then
            echo "  ❌ Senzing SDK not installed"
            echo "     Fix: Rebuild API container (docker compose build api)"
        fi

        if [ "$LICENSE_CONFIGURED" = "false" ]; then
            echo "  ❌ License not found"
            echo "     Fix: Place g2.lic in api/secrets/senzing/"
            echo "     Or: Place base64 encoded license in api/g2license_*/g2.lic_base64"
        fi

        if [ "$CLIENT_INITIALIZED" = "false" ]; then
            echo "  ❌ Senzing client not initialized"
            echo "     Fix: Check if Senzing gRPC server is running"
            echo "     Run: docker compose ps senzing-grpc"
            echo "     Logs: docker compose logs senzing-grpc"
        fi

        echo ""
        echo "See full error details above in the 'errors' array."
    fi
else
    # No jq, show raw JSON
    echo "$HEALTH_RESPONSE"
    echo ""
    echo "Install 'jq' for formatted output: brew install jq"
fi

echo ""
echo "=========================================="
echo "Additional Diagnostic Commands:"
echo "=========================================="
echo ""
echo "Check all services:"
echo "  docker compose ps"
echo ""
echo "Check Senzing gRPC server:"
echo "  docker compose logs senzing-grpc --tail=50"
echo ""
echo "Check PostgreSQL:"
echo "  docker compose logs senzing-postgres --tail=20"
echo ""
echo "View Senzing debug logs during resolution:"
echo "  ./view_senzing_debug.sh"
echo ""
