# Docker Stage 2 - CI and Production Skeleton

Stage 1 is already working:
- backend container on port 8000
- webapp container on port 3000
- redis container on port 6379
- ComfyUI stays outside Docker at host.docker.internal:8188
- Ollama stays outside Docker at host.docker.internal:11434

Stage 2 adds:
- GitHub Actions Docker CI
- optional production Dockerfiles
- optional production compose with nginx
- scripts for production dry-run

## Files added

```text
.github/workflows/docker-ci.yml
.github/workflows/prod-build-ci.yml
backend/Dockerfile.prod
webapp/Dockerfile.prod
docker-compose.prod.yml
nginx/default.conf
.env.prod.example
scripts/docker-prod-up.ps1
scripts/docker-prod-down.ps1
scripts/docker-prod-logs.ps1
scripts/docker-prod-rebuild.ps1
docs/DOCKER_STAGE2_CICD_README.md
```

## CI only

Push to GitHub. The `docker-ci.yml` workflow builds the Stage 1 Docker images. It does not deploy and it does not need secrets.

## Production dry-run locally

This is optional and should be tested after Stage 1 functional tests.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\docker-prod-up.ps1
```

Then open:

```text
http://localhost
http://localhost/docs
```

Stop:

```powershell
.\scripts\docker-prod-down.ps1
```

## Important

Do not commit real `.env` files or real API keys.

For real CD deployment, the target server is needed:
- VPS IP / hostname
- SSH user
- domain name if available
- where ComfyUI and Ollama will run
- whether SSL will be handled with Cloudflare, Nginx Proxy Manager, Traefik, or Certbot
