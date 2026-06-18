$ErrorActionPreference = "Stop"
Write-Host "Stopping containers and removing dev caches..." -ForegroundColor Yellow
docker compose down
if (Test-Path .\webapp\.next) { Remove-Item -Recurse -Force .\webapp\.next }
Write-Host "Done. Run scripts\docker-dev-up.ps1 again." -ForegroundColor Green
