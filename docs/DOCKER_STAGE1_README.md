# AI Studio Pro - Docker Stage 1

This stage dockerizes:

- FastAPI backend
- Next.js frontend
- Redis

ComfyUI and Ollama stay outside Docker for now. This is safer for Windows + GPU + local models.

## Files to copy

Copy these files/folders into the project root:

```text
docker-compose.yml
.env.docker.example
backend/Dockerfile
backend/.dockerignore
webapp/Dockerfile
webapp/.dockerignore
scripts/docker-dev-up.ps1
scripts/docker-dev-down.ps1
scripts/docker-dev-clean.ps1
.github/workflows/docker-ci.yml
```

## Before running

Make sure these are running on Windows host:

```text
ComfyUI: http://127.0.0.1:8188
Ollama:  http://127.0.0.1:11434
```

The containers will reach them through:

```text
http://host.docker.internal:8188
http://host.docker.internal:11434
```

## Required backend .env checks

In `backend/.env`, keep real values. At the bottom, make sure Stripe real mode is correct:

```env
LOCAL_CREDIT_PURCHASE_ENABLED=false
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://127.0.0.1:8000
FRONTEND_PUBLIC_URL=http://localhost:3000
BACKEND_PUBLIC_URL=http://127.0.0.1:8000
```

## Start

From project root:

```powershell
.\scripts\docker-dev-up.ps1
```

Or:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:3000
```

Backend:

```text
http://127.0.0.1:8000
```

## Stop

```powershell
.\scripts\docker-dev-down.ps1
```

## Clean frontend cache

```powershell
.\scripts\docker-dev-clean.ps1
```

## Notes

- Do not dockerize ComfyUI in Stage 1.
- Do not put secret keys in GitHub.
- Keep `backend/.env` out of git.
- If port 3000 is busy, stop local node processes before starting Docker.
