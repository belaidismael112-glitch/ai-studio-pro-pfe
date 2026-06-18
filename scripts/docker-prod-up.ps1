$ErrorActionPreference = "Stop"
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml ps
