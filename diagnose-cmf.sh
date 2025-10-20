#!/bin/bash
# CMF Tool Diagnostic Script
# Run this on the Windows laptop to diagnose CMF tool issues
# Usage: ./diagnose-cmf.sh

echo "========================================="
echo "CMF Tool Diagnostic Report"
echo "========================================="
echo ""

# Check if Docker is running
echo "1. Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    echo "   ❌ Docker is not running"
    exit 1
else
    echo "   ✅ Docker is running"
fi
echo ""

# Get API container ID
echo "2. Finding API container..."
API_CONTAINER=$(docker compose ps -q api)
if [ -z "$API_CONTAINER" ]; then
    echo "   ❌ API container not found. Run: docker compose up -d"
    exit 1
else
    echo "   ✅ API container ID: $API_CONTAINER"
fi
echo ""

# Check if container is running
echo "3. Checking if API container is running..."
if ! docker ps --filter "id=$API_CONTAINER" --format "{{.Status}}" | grep -q "Up"; then
    echo "   ❌ API container is not running"
    exit 1
else
    echo "   ✅ API container is running"
fi
echo ""

# Check CMF tool file exists
echo "4. Checking CMF tool file existence..."
docker exec "$API_CONTAINER" test -f /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool
if [ $? -eq 0 ]; then
    echo "   ✅ CMF tool file exists"
else
    echo "   ❌ CMF tool file NOT found"
    exit 1
fi
echo ""

# Check CMF tool permissions
echo "5. Checking CMF tool permissions..."
PERMS=$(docker exec "$API_CONTAINER" stat -c "%A" /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool 2>/dev/null)
if [ -z "$PERMS" ]; then
    echo "   ❌ Cannot check permissions (stat command failed)"
else
    echo "   Permissions: $PERMS"
    if [[ $PERMS =~ ^.*x ]]; then
        echo "   ✅ CMF tool is executable"
    else
        echo "   ❌ CMF tool is NOT executable"
        echo "   → Container needs to be rebuilt with chmod +x"
    fi
fi
echo ""

# Check Java availability
echo "6. Checking Java installation..."
JAVA_VERSION=$(docker exec "$API_CONTAINER" java -version 2>&1 | head -n 1)
if [ $? -eq 0 ]; then
    echo "   ✅ Java is installed: $JAVA_VERSION"
else
    echo "   ❌ Java is NOT installed"
fi
echo ""

# Try to run CMF tool
echo "7. Testing CMF tool execution..."
CMF_OUTPUT=$(docker exec "$API_CONTAINER" /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool version 2>&1)
CMF_EXIT=$?
if [ $CMF_EXIT -eq 0 ]; then
    echo "   ✅ CMF tool executed successfully"
    echo "   Version: $CMF_OUTPUT"
else
    echo "   ❌ CMF tool execution FAILED"
    echo "   Exit code: $CMF_EXIT"
    echo "   Output:"
    echo "$CMF_OUTPUT" | sed 's/^/      /'
fi
echo ""

# Check recent API logs for CMF errors
echo "8. Checking recent API logs for CMF errors..."
echo "   Last 20 lines containing 'CMF' or 'error':"
docker compose logs api --tail=100 2>/dev/null | grep -i -E "(cmf|error)" | tail -20 | sed 's/^/   /'
echo ""

# Summary
echo "========================================="
echo "Diagnostic Summary"
echo "========================================="
if [ $CMF_EXIT -eq 0 ]; then
    echo "✅ CMF tool is working correctly"
    echo ""
    echo "If you're still getting 400 errors, they are likely"
    echo "legitimate validation errors. Check the error response"
    echo "body for specific schema issues."
else
    echo "❌ CMF tool is NOT working"
    echo ""
    echo "Next steps:"
    echo "1. Rebuild the container:"
    echo "   docker compose down"
    echo "   docker compose up -d --build"
    echo ""
    echo "2. Run this diagnostic script again"
    echo ""
    echo "3. If still failing, check the error output above"
fi
echo ""
