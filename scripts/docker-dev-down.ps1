$ErrorActionPreference = "Stop"
Write-Host "Stopping AI Studio Docker stack..." -ForegroundColor Cyan
docker compose down
