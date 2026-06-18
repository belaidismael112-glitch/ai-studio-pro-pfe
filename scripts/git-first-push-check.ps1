Write-Host "== First push safety check ==" -ForegroundColor Cyan
if (-not (Test-Path ".gitignore")) {
  Write-Host ".gitignore missing." -ForegroundColor Red
  exit 1
}

$mustIgnore = @(
  "backend/.env",
  "backend/ComfyUI-master/test.txt",
  "backend/venv/test.txt",
  "webapp/node_modules/test.txt",
  "webapp/.next/test.txt",
  "backend/ai_studio.db",
  "backend/app14.zip"
)

$failed = $false
foreach ($path in $mustIgnore) {
  git check-ignore -q $path
  if ($LASTEXITCODE -ne 0) {
    Write-Host "NOT ignored: $path" -ForegroundColor Red
    $failed = $true
  } else {
    Write-Host "ignored OK: $path" -ForegroundColor Green
  }
}

if ($failed) {
  Write-Host "Fix .gitignore before git add/commit." -ForegroundColor Red
  exit 1
}

Write-Host "Safe to continue with git add for normal code files." -ForegroundColor Green
