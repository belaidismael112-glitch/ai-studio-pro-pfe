# Security Policy — AI Studio Pro

AI Studio Pro applique une configuration backend orientée sécurité pour protéger les comptes, les crédits, les paiements, les fichiers téléversés et les accès administrateur.

## Périmètre du projet

Cette politique concerne la version actuelle du dépôt :

- frontend web Next.js / React ;
- backend FastAPI ;
- Redis pour cache, sessions techniques ou révocation de tokens selon configuration ;
- Stripe pour les paiements et webhooks ;
- ComfyUI et Ollama comme services IA locaux ou services d'appui ;
- Docker / Docker Compose pour l'exécution locale et la démonstration.

Les fonctions non présentes dans le code ne doivent pas être présentées comme livrées. La publication automatique vers Facebook, Instagram ou LinkedIn et le fine-tuning complet des modèles sont considérés comme des perspectives, pas comme des fonctionnalités de production actuelles.

## Mesures implémentées ou prévues dans la configuration backend

- Authentification par JWT avec access token et refresh token.
- Claims explicites dans les tokens lorsque configurés : `iss`, `aud`, `iat`, `nbf`, `exp`.
- Rotation des refresh tokens avec allowlist par utilisateur lorsque Redis est activé.
- Révocation de tokens via blacklist JTI lorsque Redis est activé.
- Contrôle d'accès par rôles : `USER`, `PREMIUM`, `ADMIN`, `SUPERADMIN`.
- Compatibilité avec l'ancien champ `is_admin` si présent dans la base.
- Protection des endpoints administrateur par vérification de rôle.
- Rate limiting via middleware backend lorsque l'option est activée.
- Headers de sécurité en production, notamment HSTS lorsque `DEBUG=false` et que l'application est servie derrière HTTPS.
- Sécurité des uploads : taille maximale, validation MIME et traitement contrôlé des fichiers multipart.
- Vérification de la signature des webhooks Stripe via `STRIPE_WEBHOOK_SECRET`.
- Séparation des secrets dans des fichiers `.env` locaux non versionnés.

## Recommandations de production

Avant tout déploiement public ou démonstration ouverte, vérifier les points suivants :

- `DEBUG=false` en production.
- HTTPS activé via un reverse proxy comme Nginx, Traefik ou Cloudflare.
- `SECRET_KEY` et `JWT_SECRET_KEY` forts, uniques et non publiés.
- `STRIPE_SECRET_KEY` conservée uniquement côté serveur.
- `STRIPE_WEBHOOK_SECRET` configuré et vérifié côté backend.
- `CORS_ORIGINS` limité aux domaines réels de l'application.
- PostgreSQL utilisé pour une production réelle.
- Redis configuré et non exposé publiquement.
- `.env` exclu de GitHub et des archives ZIP partagées.
- Logs vérifiés afin de ne pas afficher de secrets, tokens ou clés privées.
- Comptes administrateur protégés par mots de passe forts.

## Fichiers sensibles à ne pas publier

Ne jamais publier :

- `.env`
- `.env.local`
- `.env.production`
- clés Stripe réelles ou de test privées ;
- secrets JWT ;
- cookies de session ;
- captures contenant emails, tokens ou informations personnelles non nécessaires.

Publier uniquement des exemples neutres comme `.env.example` ou `.env.prod.example`.

## Signalement de vulnérabilité

Pour signaler un problème de sécurité, utiliser un canal privé du dépôt GitHub si disponible, ou contacter directement le mainteneur du projet. Ne pas publier publiquement une faille exploitable avant correction.

## Limites connues

- La sécurité finale dépend de la configuration réelle des variables d'environnement.
- Les workflows IA locaux nécessitent une isolation correcte du réseau et des fichiers.
- Les intégrations sociales automatiques ne sont pas incluses dans la version actuelle.
- Le fine-tuning complet n'est pas activé comme fonctionnalité stable de production.
