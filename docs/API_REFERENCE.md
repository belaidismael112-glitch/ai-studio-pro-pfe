# API Reference (AI Studio Pro)

Base URL: `/api/v1`

## Auth
- `POST /auth/register` — Create account
- `POST /auth/login` — Login and receive JWT access token
- `POST /auth/refresh` — Refresh access token
- `POST /auth/logout` — Revoke current token

## Users
- `GET /users/me` — Current user profile
- `PATCH /users/me` — Update profile

## Credits
- `GET /credits/balance` — Current balance (auth)
- `GET /credits/packages` — Available credit packs (public)
- `POST /credits/purchase` — Create Stripe checkout session (auth)
- `GET /credits/history` — Credit transactions (auth)

## Subscriptions
- `GET /subscriptions/current` — Current subscription (auth)
- `POST /subscriptions/checkout` — Create Stripe checkout for subscription (auth)
- `POST /subscriptions/portal` — Customer portal (auth)

## Generations
- `POST /generations` — Create generation request (auth)
- `GET /generations` — History (auth)
- `GET /generations/{id}` — Single generation (auth)

## Admin (requires admin role)
- `GET /admin/overview`
- `GET /admin/generations_per_day?days=30`
- `GET /admin/revenue?range=month`
- `GET /admin/top_models?days=30`

## Webhooks
- `POST /webhooks/stripe` — Stripe webhook endpoint (signature verified)
