# AI Studio Pro - Web Application

Application web React/Next.js pour AI Studio Pro - Plateforme de génération d'images et vidéos par IA.

## 🚀 Démarrage rapide

### Prérequis

- Node.js 18+
- npm ou yarn

### Installation

```bash
# Installer les dépendances
npm install

# Configurer les variables d'environnement
cp .env.example .env.local
# Éditer .env.local avec votre configuration

# Lancer le serveur de développement
npm run dev
```

L'application sera accessible sur `http://localhost:3000`

### Build de production

```bash
npm run build
npm start
```

## 📁 Structure du projet

```
webapp/
├── src/
│   ├── app/                    # Routes Next.js (App Router)
│   │   ├── page.tsx           # Page d'accueil
│   │   ├── layout.tsx         # Layout racine
│   │   ├── login/             # Page de connexion
│   │   ├── register/          # Page d'inscription
│   │   ├── dashboard/         # Tableau de bord
│   │   ├── generate/
│   │   │   ├── image/         # Génération d'images
│   │   │   └── video/         # Génération de vidéos
│   │   ├── history/           # Historique
│   │   ├── credits/           # Gestion des crédits
│   │   └── settings/          # Paramètres
│   │
│   ├── components/
│   │   ├── ui/                # Composants UI réutilisables
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   └── ...
│   │   └── layout/            # Composants de layout
│   │       ├── navbar.tsx
│   │       ├── sidebar.tsx
│   │       └── dashboard-layout.tsx
│   │
│   ├── hooks/                 # Hooks personnalisés
│   │   ├── useAuth.ts
│   │   ├── useGenerations.ts
│   │   └── useCredits.ts
│   │
│   ├── lib/                   # Utilitaires
│   │   ├── api.ts            # Client API
│   │   └── utils.ts          # Fonctions utilitaires
│   │
│   ├── store/                 # État global (Zustand)
│   │   └── authStore.ts
│   │
│   └── types/                 # Types TypeScript
│       └── index.ts
│
├── public/                    # Fichiers statiques
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.js
```

## 🛠️ Technologies

- **Next.js 14** - Framework React avec App Router
- **TypeScript** - Typage statique
- **Tailwind CSS** - Framework CSS utilitaire
- **Radix UI** - Composants UI headless
- **Zustand** - Gestion d'état
- **TanStack Query** - Gestion des requêtes API
- **Axios** - Client HTTP

## 🔐 Authentification

L'authentification utilise JWT tokens :
- Access token (30 min) stocké en mémoire
- Refresh token (7 jours) stocké dans localStorage
- Intercepteur Axios pour le rafraîchissement automatique

## 🎨 Thèmes

Le design system utilise Tailwind CSS avec :
- Palette de couleurs personnalisée
- Composants UI cohérents
- Mode sombre/clair (à implémenter)

## 📡 API

Les appels API sont centralisés dans `lib/api.ts` :
- `authApi` - Authentification
- `userApi` - Gestion utilisateur
- `generationApi` - Génération de contenu
- `creditsApi` - Gestion des crédits
- `subscriptionApi` - Abonnements

## 📝 Fonctionnalités

### Pages publiques
- [x] Page d'accueil
- [x] Login
- [x] Register

### Pages protégées (authentification requise)
- [x] Dashboard avec statistiques
- [x] Génération d'images
- [x] Génération de vidéos
- [x] Historique des générations
- [x] Gestion des crédits
- [x] Paramètres utilisateur

## 🚀 Déploiement

### Vercel (recommandé)

```bash
npm i -g vercel
vercel
```

### Docker

```bash
docker build -t ai-studio-pro-web .
docker run -p 3000:3000 ai-studio-pro-web
```

## 📄 Licence

MIT
