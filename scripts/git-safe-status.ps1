Write-Host "== Git safe status ==" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
  Write-Host "No .git folder yet. Git repo is not initialized." -ForegroundColor Yellow
  exit 0
}

git status --short
Write-Host ""
Write-Host "== Potential heavy/unwanted tracked candidates ==" -ForegroundColor Cyan
$patterns = @(
  "ComfyUI-master", "venv", "venv_comfy", "node_modules", ".next", "static", "tmp", "logs", "_v", "_backup", ".env", ".db", ".sqlite", ".zip"
)
$files = git ls-files --others --cached --exclude-standard
$hits = @()
foreach ($f in $files) {
  foreach ($p in $patterns) {
    if ($f -like "*$p*") { $hits += $f; break }
  }
}
if ($hits.Count -eq 0) {
  Write-Host "No obvious heavy/secret candidates found in git view." -ForegroundColor Green
} else {
  $hits | Select-Object -First 80
  Write-Host "Review these before commit. Do NOT commit secrets/heavy runtime folders." -ForegroundColor Red
}
