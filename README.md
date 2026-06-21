# AI Studio Pro

<p align="center">
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
</p>

## Application Professionnelle de GÃ©nÃ©ration d'Images et VidÃ©os par Intelligence Artificielle

![Studio Pro Workspace](assets/studio-pro-workspace-logo-master.png)
![Studio Pro Workspace](assets/studio-pro-workspace-logo-master.png)
![Studio Pro Workspace](assets/studio-pro-workspace-logo-master.png)
![Studio Pro Workspace](assets/studio-pro-workspace-logo-master.png)

---

## ðŸ“‹ Table des matiÃ¨res

- [PrÃ©sentation](#prÃ©sentation)
- [Architecture](#architecture)
- [FonctionnalitÃ©s](#fonctionnalitÃ©s)
- [Installation](#installation)
- [Structure du projet](#structure-du-projet)
- [Technologies](#technologies)
- [Documentation](#documentation)
- [Auteur](#auteur)

---

## ðŸŽ¯ PrÃ©sentation

**AI Studio Pro** est une plateforme professionnelle permettant la gÃ©nÃ©ration d'images et de vidÃ©os par intelligence artificielle. L'application est accessible via :

- âœ… **Application Desktop Windows** (PySide6/Qt)
- âœ… **Application Web** (React/Next.js)
- âœ… **API REST** (FastAPI)

Le systÃ¨me utilise des modÃ¨les AI cloud (Stable Diffusion, Runway) pour garantir des performances optimales sans nÃ©cessiter de matÃ©riel puissant cÃ´tÃ© client.

---

## ðŸ—ï¸ Architecture

<p align="center">
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
</p>

## ðŸ–¥ï¸ AperÃ§u (Screenshots)

<p align="center">
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
  <br/>
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
  <br/>
  <img src="assets/studio-pro-workspace-logo-master.png" alt="Studio Pro Workspace" width="720">
</p>

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                        AI Studio Pro                             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚   Desktop    â”‚      â”‚     Web      â”‚      â”‚  Mobile App  â”‚  â”‚
â”‚  â”‚  (PySide6)   â”‚      â”‚  (React)     â”‚      â”‚   (Future)   â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚         â”‚                      â”‚                                 â”‚
â”‚         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                 â”‚
â”‚                    â”‚                                             â”‚
â”‚         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                 â”‚
â”‚         â”‚   API Gateway        â”‚                                 â”‚
â”‚         â”‚   (FastAPI)          â”‚                                 â”‚
â”‚         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                 â”‚
â”‚                    â”‚                                             â”‚
â”‚    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                            â”‚
â”‚    â”‚               â”‚               â”‚                            â”‚
â”‚ â”Œâ”€â”€â–¼â”€â”€â”€â”     â”Œâ”€â”€â”€â”€â–¼â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”                      â”‚
â”‚ â”‚Auth  â”‚     â”‚ Credits â”‚    â”‚Generation â”‚                      â”‚
â”‚ â”‚JWT   â”‚     â”‚ System  â”‚    â”‚  Service  â”‚                      â”‚
â”‚ â””â”€â”€â”¬â”€â”€â”€â”˜     â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”˜                      â”‚
â”‚    â”‚                                   â”‚                         â”‚
â”‚    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                         â”‚
â”‚                   â”‚                                              â”‚
â”‚         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                   â”‚
â”‚         â”‚  PostgreSQL + S3   â”‚                                   â”‚
â”‚         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                   â”‚
â”‚                                                                  â”‚
â”‚         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                                   â”‚
â”‚         â”‚  AI Services       â”‚                                   â”‚
â”‚         â”‚  (Replicate/Runway)â”‚                                   â”‚
â”‚         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                                   â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## âœ¨ FonctionnalitÃ©s

### ðŸ–¼ï¸ GÃ©nÃ©ration d'Images
- Prompts textuels avec styles prÃ©dÃ©finis
- RÃ©solutions multiples (512x512 Ã  1920x1080)
- Negative prompts pour un meilleur contrÃ´le
- Historique complet des gÃ©nÃ©rations

### ðŸŽ¬ GÃ©nÃ©ration de VidÃ©os
- Transformation de texte en vidÃ©o
- DurÃ©es configurables (2-16 secondes)
- RÃ©solutions HD disponibles
- Export au format MP4

### ðŸ’Ž SystÃ¨me de CrÃ©dits
- CrÃ©dits offerts Ã  l'inscription (100 crÃ©dits)
- Achat de packs de crÃ©dits
- Abonnements mensuels avec crÃ©dits inclus
- Historique des transactions

### ðŸ’³ Paiements
- IntÃ©gration Stripe sÃ©curisÃ©e
- Paiements par carte bancaire
- Gestion des abonnements
- Webhooks pour synchronisation

### ðŸ”’ SÃ©curitÃ©
- Authentification JWT
- ClÃ©s API protÃ©gÃ©es cÃ´tÃ© serveur
- Rate limiting
- Validation des donnÃ©es

---

## ðŸš€ Installation

### PrÃ©requis

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (optionnel, SQLite par dÃ©faut)
- Compte Stripe (pour les paiements)
- ClÃ© API Replicate (pour la gÃ©nÃ©ration AI)

### Installation automatique

**Windows :**
```bash
install.bat
```

**Linux/Mac :**
```bash
chmod +x install.sh
./install.sh
```

### Installation manuelle

#### 1. Backend

```bash
cd backend

# CrÃ©er l'environnement virtuel
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Installer les dÃ©pendances
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Ã‰diter .env avec vos clÃ©s API

# Lancer le serveur
uvicorn main:app --reload
```

#### 2. Application Desktop

```bash
cd desktop

python -m venv venv
venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Lancer l'application
python main.py
```

#### 3. Application Web

```bash
cd webapp

npm install

# Configuration
cp .env.example .env.local
# Ã‰diter .env.local

# Lancer le serveur de dÃ©veloppement
npm run dev
```

### Build ExÃ©cutable Windows

```bash
cd desktop
pyinstaller build.spec
```

L'exÃ©cutable sera crÃ©Ã© dans `dist/AI Studio Pro.exe`

---

## ðŸ“ Structure du projet

```
ai_studio_pro/
â”œâ”€â”€ ðŸ“ backend/                    # Backend FastAPI
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ core/                 # Configuration, sÃ©curitÃ©
â”‚   â”‚   â”œâ”€â”€ models/               # ModÃ¨les SQLAlchemy
â”‚   â”‚   â”œâ”€â”€ schemas/              # ModÃ¨les Pydantic
â”‚   â”‚   â”œâ”€â”€ services/             # Logique mÃ©tier
â”‚   â”‚   â””â”€â”€ api/v1/endpoints/     # Routes API
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â”œâ”€â”€ Dockerfile
â”‚   â””â”€â”€ docker-compose.yml
â”‚
â”œâ”€â”€ ðŸ“ desktop/                    # Application Desktop PySide6
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ core/                 # Configuration, thÃ¨mes
â”‚   â”‚   â”œâ”€â”€ api/                  # Client HTTP
â”‚   â”‚   â””â”€â”€ ui/                   # Interface utilisateur
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ build.spec
â”‚   â””â”€â”€ requirements.txt
â”‚
â”œâ”€â”€ ðŸ“ webapp/                     # Application Web React/Next.js
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ app/                  # Routes Next.js
â”‚   â”‚   â”œâ”€â”€ components/           # Composants React
â”‚   â”‚   â”œâ”€â”€ hooks/                # Hooks personnalisÃ©s
â”‚   â”‚   â”œâ”€â”€ lib/                  # Utilitaires
â”‚   â”‚   â”œâ”€â”€ store/                # Ã‰tat global (Zustand)
â”‚   â”‚   â””â”€â”€ types/                # Types TypeScript
â”‚   â”œâ”€â”€ package.json
â”‚   â””â”€â”€ next.config.js
â”‚
â”œâ”€â”€ ðŸ“ rapport_pfe/               # Rapport PFE
â”‚   â””â”€â”€ Rapport_PFE_AI_Studio_Pro.docx
â”‚
â”œâ”€â”€ README.md
â”œâ”€â”€ install.bat / install.sh
â””â”€â”€ LICENSE
```

---

## ðŸ› ï¸ Technologies

### Backend
- **FastAPI** - Framework web Python haute performance
- **SQLAlchemy** - ORM pour bases de donnÃ©es
- **PostgreSQL** - Base de donnÃ©es relationnelle
- **JWT** - Authentification par tokens
- **Stripe** - Paiements en ligne
- **Replicate API** - GÃ©nÃ©ration d'images/vidÃ©os AI

### Desktop
- **PySide6** - Framework Qt pour Python
- **httpx** - Client HTTP asynchrone
- **QSS** - Feuilles de style Qt

### Web
- **Next.js 14** - Framework React
- **TypeScript** - Typage statique
- **Tailwind CSS** - Framework CSS utilitaire
- **Radix UI** - Composants UI headless
- **Zustand** - Gestion d'Ã©tat
- **TanStack Query** - Gestion des requÃªtes API

---

## ðŸ“š Documentation

- [Rapport PFE](rapport_pfe/Rapport_PFE_AI_Studio_Pro.docx) - Document complet du projet
- [Documentation Backend](backend/README.md)
- [Documentation Desktop](desktop/README.md)
- [Documentation Web](webapp/README.md)

---

## ðŸ‘¤ Auteur

**Projet de Fin d'Ã‰tudes**

- Ã‰tudiant : [Nom de l'Ã©tudiant]
- Encadrant : [Nom de l'encadrant]
- UniversitÃ© : [Nom de l'universitÃ©]
- AnnÃ©e universitaire : 2024-2025

---

## ðŸ“„ Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de dÃ©tails.

---

## ðŸ™ Remerciements

- Replicate pour l'API de gÃ©nÃ©ration AI
- Stripe pour les services de paiement
- La communautÃ© open source pour les outils utilisÃ©s

---

<p align="center">
  <strong>AI Studio Pro</strong> - LibÃ©rez votre crÃ©ativitÃ© avec l'IA
</p>


## Database

![Studio Pro Workspace](assets/studio-pro-workspace-logo-master.png)

## Tests (Backend)

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

## Documentation

- `docs/API_REFERENCE.md`
- `docs/DB_SCHEMA.md`
- `docs/PROD_CHECKLIST.md`

