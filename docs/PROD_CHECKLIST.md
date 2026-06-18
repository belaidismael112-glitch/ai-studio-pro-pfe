# Production Checklist (Quick)

## Secrets
- Set `SECRET_KEY`, `JWT_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` as environment variables
- Never commit `.env` files

## HTTPS
- Run behind HTTPS (reverse proxy: Nginx/Caddy/Traefik)
- Enable HSTS only when HTTPS is active

## CORS
- Set `CORS_ORIGINS` to your real frontend domains (avoid `*` in production)

## Stripe
- Webhooks MUST verify signature (`STRIPE_WEBHOOK_SECRET`)
- Handle replay safely (store processed `event_id` in `webhook_events`)

## Database safety
- Use transactions when decreasing credits + creating generations
- Ensure atomic credit updates (row locking / safe update)

## Background jobs
- Long AI calls must run in Celery tasks (avoid request timeouts)

## Observability
- Enable structured logs
- Monitor worker health + queue depth
