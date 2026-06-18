# AI Studio Pro — Security Notes

This project includes a "secure by default" backend configuration.

## Implemented

- **JWT** access + refresh tokens with explicit claims (`iss`, `aud`, `iat`, `nbf`, `exp`) and a configurable leeway.
- **Refresh token rotation** with an allowlist (per-user) stored in Redis.
- **Token revocation** via JTI blacklist stored in Redis.
- **Rate limiting** using SlowAPI middleware.
- **Security headers** middleware (HSTS enabled when not in DEBUG).
- **Upload safety** for multipart endpoints:
  - MIME allowlist
  - max upload size (`MAX_UPLOAD_MB`)
- **Stripe webhooks** signature verification via `STRIPE_WEBHOOK_SECRET`.

## RBAC

The `users` table supports a `role` field:

- `USER` (default)
- `PREMIUM`
- `ADMIN`
- `SUPERADMIN`

Backward compatibility is maintained with the legacy `is_admin` flag.

Use `app.core.roles.require_role(Role.ADMIN)` for admin endpoints.

## Recommended Production Settings

- Run behind HTTPS (reverse proxy: Nginx / Traefik).
- Set `DEBUG=false`.
- Use strong secrets for `SECRET_KEY` and `JWT_SECRET_KEY`.
- Use PostgreSQL for production.
- Configure Redis for persistence.

## Deployment Checklist (No “thaghrat”)

- [ ] **Do not ship secrets**: keep `.env` out of Git/ZIP; use `.env.example` only.
- [ ] **Stripe**: set `STRIPE_WEBHOOK_SECRET` (required) and keep `STRIPE_SECRET_KEY` server-side only.
- [ ] **CORS**: set `CORS_ORIGINS` to your real frontends (avoid `*` in production).
- [ ] **HTTPS**: enforce TLS at the reverse proxy; keep HSTS enabled.
- [ ] **Updates (desktop)**: prefer signed installers / checksum verification for enterprise deployment.
