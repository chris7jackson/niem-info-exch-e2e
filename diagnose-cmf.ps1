# CMF Tool Diagnostic Script for Windows PowerShell
# Run this on the Windows laptop to diagnose CMF tool issues
# Usage: .\diagnose-cmf.ps1

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "CMF Tool Diagnostic Report" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "1. Checking Docker status..." -ForegroundColor Yellow
try {
    $null = docker info 2>&1
    Write-Host "   ✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Docker is not running" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Get API container ID
Write-Host "2. Finding API container..." -ForegroundColor Yellow
$apiContainer = docker compose ps -q api
if ([string]::IsNullOrEmpty($apiContainer)) {
    Write-Host "   ❌ API container not found. Run: docker compose up -d" -ForegroundColor Red
    exit 1
} else {
    Write-Host "   ✅ API container ID: $apiContainer" -ForegroundColor Green
}
Write-Host ""

# Check if container is running
Write-Host "3. Checking if API container is running..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "id=$apiContainer" --format "{{.Status}}"
if ($containerStatus -match "Up") {
    Write-Host "   ✅ API container is running" -ForegroundColor Green
} else {
    Write-Host "   ❌ API container is not running" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Check CMF tool file exists
Write-Host "4. Checking CMF tool file existence..." -ForegroundColor Yellow
$fileCheck = docker exec $apiContainer test -f /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ CMF tool file exists" -ForegroundColor Green
} else {
    Write-Host "   ❌ CMF tool file NOT found" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Check CMF tool permissions
Write-Host "5. Checking CMF tool permissions..." -ForegroundColor Yellow
$perms = docker exec $apiContainer stat -c "%A" /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool 2>&1
if ($perms -match "x") {
    Write-Host "   Permissions: $perms" -ForegroundColor Gray
    Write-Host "   ✅ CMF tool is executable" -ForegroundColor Green
} else {
    Write-Host "   Permissions: $perms" -ForegroundColor Gray
    Write-Host "   ❌ CMF tool is NOT executable" -ForegroundColor Red
    Write-Host "   → Container needs to be rebuilt with chmod +x" -ForegroundColor Yellow
}
Write-Host ""

# Check Java availability
Write-Host "6. Checking Java installation..." -ForegroundColor Yellow
$javaVersion = docker exec $apiContainer java -version 2>&1 | Select-Object -First 1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Java is installed: $javaVersion" -ForegroundColor Green
} else {
    Write-Host "   ❌ Java is NOT installed" -ForegroundColor Red
}
Write-Host ""

# Try to run CMF tool
Write-Host "7. Testing CMF tool execution..." -ForegroundColor Yellow
$cmfOutput = docker exec $apiContainer /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool version 2>&1
$cmfExit = $LASTEXITCODE
if ($cmfExit -eq 0) {
    Write-Host "   ✅ CMF tool executed successfully" -ForegroundColor Green
    Write-Host "   Version: $cmfOutput" -ForegroundColor Gray
} else {
    Write-Host "   ❌ CMF tool execution FAILED" -ForegroundColor Red
    Write-Host "   Exit code: $cmfExit" -ForegroundColor Gray
    Write-Host "   Output:" -ForegroundColor Gray
    $cmfOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor Gray }
}
Write-Host ""

# Check recent API logs for CMF errors
Write-Host "8. Checking recent API logs for CMF errors..." -ForegroundColor Yellow
Write-Host "   Last 20 lines containing 'CMF' or 'error':" -ForegroundColor Gray
$logs = docker compose logs api --tail=100 2>&1 | Select-String -Pattern "(cmf|error)" -CaseSensitive:$false | Select-Object -Last 20
$logs | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
Write-Host ""

# Summary
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Diagnostic Summary" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
if ($cmfExit -eq 0) {
    Write-Host "✅ CMF tool is working correctly" -ForegroundColor Green
    Write-Host ""
    Write-Host "If you're still getting 400 errors, they are likely" -ForegroundColor Yellow
    Write-Host "legitimate validation errors. Check the error response" -ForegroundColor Yellow
    Write-Host "body for specific schema issues." -ForegroundColor Yellow
} else {
    Write-Host "❌ CMF tool is NOT working" -ForegroundColor Red
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Rebuild the container:" -ForegroundColor White
    Write-Host "   docker compose down" -ForegroundColor Gray
    Write-Host "   docker compose up -d --build" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Run this diagnostic script again" -ForegroundColor White
    Write-Host ""
    Write-Host "3. If still failing, check the error output above" -ForegroundColor White
}
Write-Host ""
