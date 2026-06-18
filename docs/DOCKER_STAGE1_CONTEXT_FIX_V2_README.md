# Docker Stage 1 context fix v2

Install over the project root that contains `backend/`, `webapp/`, and `docker-compose.yml`.

This replaces only:
- `backend/.dockerignore`
- `webapp/.dockerignore`
- `scripts/docker-context-check.ps1`

It excludes local venvs, ComfyUI, generated/static files, zips, old patch backups, and Next/node cache from Docker build context.
