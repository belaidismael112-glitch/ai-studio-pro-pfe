$ErrorActionPreference = "Stop"
docker compose -f docker-compose.prod.yml logs -f --tail=120
