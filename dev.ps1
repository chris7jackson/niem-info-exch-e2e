# Development helper script for multi-worktree workflows (PowerShell)
# Automatically assigns unique ports based on directory name
# Usage: .\dev.ps1 [docker compose commands]
# Examples:
#   .\dev.ps1 up -d
#   .\dev.ps1 down
#   .\dev.ps1 logs -f api
#   .\dev.ps1 ps

# Get directory name and create hash for unique port offset
$dirName = Split-Path -Leaf (Get-Location)

# Create a simple hash from directory name
$bytes = [System.Text.Encoding]::UTF8.GetBytes($dirName)
$hash = 0
foreach ($byte in $bytes) {
    $hash = ($hash * 31 + $byte) % 1000000
}
$portOffset = $hash % 50

# Calculate unique ports
$env:API_PORT = 8000 + $portOffset
$env:UI_PORT = 3000 + $portOffset
$env:COMPOSE_PROJECT_NAME = "niem-$dirName"

# Display configuration
Write-Host "🚀 Starting development environment for: $dirName" -ForegroundColor Green
Write-Host "   Project: $env:COMPOSE_PROJECT_NAME"
Write-Host "   API Port: $env:API_PORT"
Write-Host "   UI Port: $env:UI_PORT"
Write-Host ""

# Check if shared infrastructure is running
$infraExists = docker network inspect niem-infra 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Using shared infrastructure (niem-infra network)" -ForegroundColor Green
} else {
    Write-Host "⚠️  Shared infrastructure not found." -ForegroundColor Yellow
    Write-Host "   To start shared infrastructure:"
    Write-Host "   docker compose -f docker-compose.infra.yml up -d"
    Write-Host ""
    Write-Host "   Continuing with local infrastructure..."
    Write-Host ""
}

# Pass all arguments to docker compose
$allArgs = $args -join ' '
Invoke-Expression "docker compose $allArgs"
