# Stage 3 - Safe GitHub and CI activation

This stage prepares the project for GitHub without committing heavy local runtime folders or secrets.

## What this stage adds

- A safer root `.gitignore`
- `scripts/git-safe-status.ps1`
- `scripts/git-first-push-check.ps1`
- `scripts/git-init-and-first-commit.ps1`

## Important

Do not commit:

- `backend/.env`
- `webapp/.env`
- `backend/ComfyUI-master/`
- `backend/venv/`
- `backend/venv_comfy/`
- `webapp/node_modules/`
- `webapp/.next/`
- `backend/static/`, `static/`, `tmp/`, `logs/`
- local `.db`, `.sqlite`, `.zip` files

## Recommended sequence

From project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
powershell -ExecutionPolicy Bypass -File .\scripts\git-first-push-check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\git-safe-status.ps1
```

If the checks are clean and you have a GitHub remote URL:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\git-init-and-first-commit.ps1 -RemoteUrl "https://github.com/YOUR_USER/YOUR_REPO.git"
```

If you prefer manual commands:

```powershell
git init
git status --short
git add .
git status --short
git commit -m "chore: dockerize ai studio stage 1 and add ci skeleton"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Before `git commit`, inspect `git status --short`. If any secret or heavy folder appears, stop and fix `.gitignore`.

## CI

The Stage 2 workflows should run automatically on GitHub after push:

- `.github/workflows/docker-ci.yml`
- `.github/workflows/prod-build-ci.yml`
