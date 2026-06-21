# API Reference — AI Studio Pro

Base URL: `/api/v1`

> Les noms exacts peuvent évoluer selon les fichiers de routes du backend. Cette référence décrit le périmètre fonctionnel attendu du projet.

## Authentification

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Créer un compte utilisateur. |
| POST | `/auth/login` | Se connecter et obtenir un access token. |
| POST | `/auth/refresh` | Renouveler un access token. |
| POST | `/auth/logout` | Révoquer la session courante. |

## Utilisateur

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/users/me` | Récupérer le profil courant. |
| PATCH | `/users/me` | Mettre à jour le profil. |

## Crédits

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/credits/balance` | Consulter le solde de crédits. |
| GET | `/credits/packages` | Lister les packs disponibles. |
| POST | `/credits/checkout` | Créer une session Stripe Checkout. |
| GET | `/credits/history` | Consulter l'historique des transactions. |

## Génération

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/generations` | Lancer une génération texte-vers-image. |
| POST | `/image-to-image` | Transformer une image source. |
| GET | `/generations` | Consulter l'historique. |
| GET | `/generations/{id}` | Consulter un résultat précis. |
| DELETE | `/generations/{id}` | Supprimer un résultat si autorisé. |

## Assistant et analyse

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/assistant` | Demander une aide ou un plan assisté. |
| POST | `/operator` | Préparer ou lancer un plan assisté. |
| POST | `/analysis/neural-camera` | Analyser une image source. |
| POST | `/audience-mirror` | Analyser un contenu par audience cible. |

## Administration

Ces routes nécessitent un rôle `ADMIN` ou supérieur.

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/admin/overview` | Tableau de bord global. |
| GET | `/admin/users` | Gestion des utilisateurs. |
| GET | `/admin/generations` | Modération des générations. |
| GET | `/admin/reclamations` | Gestion des réclamations. |
| GET | `/admin/top-models` | Comparaison et statistiques modèles. |

## Webhooks

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/webhooks/stripe` | Réception des événements Stripe avec vérification de signature. |
