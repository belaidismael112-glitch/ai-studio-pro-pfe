$ErrorActionPreference = "Stop"

Write-Host "Stopping local Node processes that may occupy port 3000..." -ForegroundColor Yellow
try { taskkill /F /IM node.exe | Out-Null } catch {}

Write-Host "Starting AI Studio Docker stack..." -ForegroundColor Cyan
docker compose up --build
