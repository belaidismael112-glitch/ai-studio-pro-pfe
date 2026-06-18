param(
  [string]$RemoteUrl = ""
)

Write-Host "== Git init and first commit helper ==" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
  git init
}

git add .
Write-Host ""
Write-Host "== Staged files preview ==" -ForegroundColor Cyan
git status --short
Write-Host ""
Write-Host "Review the list. If you see .env, ComfyUI-master, venv, node_modules, .next, static, tmp, logs, db or zip files, STOP." -ForegroundColor Yellow
$answer = Read-Host "Type COMMIT to create the first commit"
if ($answer -ne "COMMIT") {
  Write-Host "Commit cancelled." -ForegroundColor Yellow
  exit 0
}

git commit -m "chore: dockerize ai studio stage 1 and add ci skeleton"

if ($RemoteUrl -ne "") {
  git branch -M main
  git remote remove origin 2>$null
  git remote add origin $RemoteUrl
  git push -u origin main
}
