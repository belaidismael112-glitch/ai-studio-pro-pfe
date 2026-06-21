# Checklist production — AI Studio Pro

## Secrets

- [ ] `.env` non versionné.
- [ ] `SECRET_KEY` fort et unique.
- [ ] `JWT_SECRET_KEY` fort et unique.
- [ ] `STRIPE_SECRET_KEY` uniquement côté serveur.
- [ ] `STRIPE_WEBHOOK_SECRET` configuré.

## Backend

- [ ] `DEBUG=false`.
- [ ] `/docs` désactivé ou protégé en production.
- [ ] CORS limité aux domaines autorisés.
- [ ] Rate limiting activé.
- [ ] Uploads limités par taille et MIME.
- [ ] Logs sans secrets.

## Frontend

- [ ] Variables publiques seulement dans `NEXT_PUBLIC_*`.
- [ ] Aucune clé secrète dans le frontend.
- [ ] Build production testé.

## Base de données

- [ ] PostgreSQL utilisé en production.
- [ ] Migrations testées.
- [ ] Sauvegarde configurée.
- [ ] Transactions critiques pour crédits et paiements.

## Redis

- [ ] Redis configuré pour les tokens/cache.
- [ ] Persistance activée si nécessaire.
- [ ] Accès non exposé publiquement.

## Stripe

- [ ] Webhook endpoint configuré dans Stripe Dashboard.
- [ ] Signature webhook vérifiée.
- [ ] Idempotence webhook activée.
- [ ] Tests avec Stripe CLI effectués.

## IA locale

- [ ] ComfyUI lancé et accessible.
- [ ] Ollama lancé et accessible.
- [ ] Modèles requis installés.
- [ ] Timeouts et erreurs IA gérés proprement.

## Déploiement

- [ ] HTTPS actif.
- [ ] HSTS activé uniquement derrière HTTPS.
- [ ] Docker images construites.
- [ ] GitHub Actions passe avec succès.
- [ ] Cloudflare Tunnel testé si utilisé pour la démonstration.
