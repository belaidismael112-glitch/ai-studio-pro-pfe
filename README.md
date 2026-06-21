# AI Studio Pro

<p align="center">
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
</p>

**AI Studio Pro** est une plateforme web professionnelle de génération et de transformation d'images par intelligence artificielle. Elle permet de créer des visuels commerciaux à partir de prompts texte ou d'images sources, avec un système de crédits, un espace utilisateur, un espace administrateur et des services IA locaux.

## Table des matières

- [Présentation](#présentation)
- [Fonctionnalités principales](#fonctionnalités-principales)
- [Architecture](#architecture)
- [Technologies](#technologies)
- [Installation locale](#installation-locale)
- [Docker](#docker)
- [Sécurité](#sécurité)
- [Documentation](#documentation)
- [Auteur](#auteur)
- [Licence](#licence)

## Présentation

AI Studio Pro a été développé dans le cadre d'un Projet de Fin d'Études. L'objectif est de proposer une plateforme capable d'aider les utilisateurs à produire des contenus visuels de qualité professionnelle, notamment pour des usages publicitaires, marketing et créatifs.

La plateforme couvre principalement :

- la génération texte-vers-image ;
- la transformation image-vers-image ;
- les modes spécialisés : identité/personne, publicité produit, flyer/poster, remplacement d'arrière-plan et référence créative ;
- l'assistance IA pour préparer des plans de génération et améliorer les prompts ;
- l'analyse de sources visuelles et la comparaison des modèles ;
- la gestion des crédits, des utilisateurs, des historiques et des réclamations.

La version actuelle prépare des images et contenus prêts à être utilisés manuellement sur des canaux comme Facebook, Instagram ou LinkedIn. Elle ne réalise pas de publication automatique vers ces plateformes.

## Fonctionnalités principales

### Génération d'images

- Prompt textuel avec options de style et de taille.
- Negative prompt pour contrôler les éléments à éviter.
- Prévisualisation du résultat généré.
- Sauvegarde dans l'historique.
- Débit de crédits après génération.

### Image-to-Image

- Téléversement d'une image source.
- Analyse de la source avant transformation.
- Choix d'un mode dédié :
  - Auto Smart ;
  - Person / Identity ;
  - Product Ad ;
  - Flyer / Poster ;
  - Background Replace ;
  - Creative Reference.
- Contrôle de cohérence avec le principe source-lock/final-only.

### Assistant et outils IA

- Operator pour guider la préparation d'une génération.
- Director Mode et Prompt Doctor pour transformer une idée en plan exploitable.
- Audience Mirror pour vérifier l'adaptation à une cible.
- Launch Pack pour préparer un pack marketing à partir d'une idée de marque.

### Administration

- Tableau de bord administrateur.
- Gestion des utilisateurs.
- Gestion des crédits.
- Suivi des générations.
- Gestion des réclamations.
- Comparaison de modèles et suivi des performances.

### Paiement et crédits

- Compte utilisateur avec crédits disponibles.
- Intégration Stripe pour l'achat de crédits.
- Webhook Stripe côté backend.
- Historique des transactions et des générations.

## Architecture

L'application repose sur une architecture modulaire :

```text
Utilisateur / Administrateur
        |
        v
Frontend Next.js / React
        |
        v
Backend FastAPI
        |
        +--> Base de données
        +--> Redis
        +--> Stripe
        +--> ComfyUI
        +--> Ollama
        +--> Stockage des résultats
```

### Rôle des principaux composants

| Composant | Rôle |
|---|---|
| Frontend Next.js | Interface web, pages utilisateur, dashboard, génération, historique et administration |
| Backend FastAPI | API REST, authentification, crédits, orchestration métier, sécurité |
| Redis | Cache, sessions techniques, rotation/révocation de tokens selon configuration |
| Stripe | Paiement et webhooks de synchronisation |
| ComfyUI | Exécution locale des workflows IA de génération et transformation d'images |
| Ollama | Assistant local, analyse et aide à la décision selon les modules |
| Docker | Conteneurisation du frontend, backend et services d'appui |
| GitHub Actions | Intégration continue et vérifications automatisées |
| Cloudflare Tunnel | Exposition contrôlée de la démonstration si nécessaire |

## Technologies

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Zustand / gestion d'état frontend selon les modules

### Backend

- Python
- FastAPI
- SQLAlchemy
- JWT
- Redis
- Stripe Webhooks
- SlowAPI pour le rate limiting

### Intelligence artificielle

- ComfyUI pour les workflows de génération et de transformation d'images.
- Ollama pour l'assistant, l'analyse et certains modules d'aide.

### DevOps

- Docker et Docker Compose
- GitHub Actions
- Cloudflare Tunnel pour la démonstration

## Installation locale

### Prérequis

- Python 3.11+
- Node.js 18+
- Git
- Docker Desktop recommandé
- Redis si lancement hors Docker
- ComfyUI et Ollama si les workflows IA locaux sont utilisés

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou sous Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

### Frontend

Selon le nom du dossier frontend dans le dépôt :

```bash
cd frontend
npm install
npm run dev
```

ou, si le projet utilise `webapp` :

```bash
cd webapp
npm install
npm run dev
```

## Docker

Lancement local avec Docker Compose :

```bash
docker compose up --build
```

Pour un environnement de production, utiliser les fichiers de configuration de production et vérifier les variables d'environnement avant le déploiement.

## Sécurité

Le projet applique une logique de sécurité backend :

- authentification JWT ;
- tokens d'accès et refresh tokens ;
- rotation et révocation des tokens selon configuration ;
- contrôle des rôles utilisateur ;
- limitation du débit des requêtes ;
- validation des fichiers uploadés ;
- vérification des signatures Stripe Webhooks ;
- headers de sécurité lorsque le mode production est activé.

Les secrets ne doivent jamais être publiés dans GitHub. Utiliser uniquement des fichiers `.env.example` sans valeurs sensibles.

## Documentation

Les documents techniques sont disponibles dans le dossier `docs/` :

- `docs/API_REFERENCE.md`
- `docs/DB_SCHEMA.md`
- `docs/PROD_CHECKLIST.md`
- `docs/GITHUB_CLEANUP.md`

## Auteur

Projet de Fin d'Études réalisé par **Ismail Belaid**.

Encadrante académique : **Mme Sawssen JALEL**  
Encadrant professionnel : **M. Issam Ben Othmen**

## Licence

Ce projet est fourni sous licence MIT. Voir le fichier `LICENSE` pour plus d'informations.
