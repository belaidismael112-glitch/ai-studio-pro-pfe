# Nettoyage GitHub — AI Studio Pro

Ce fichier explique quoi corriger avant de publier le dépôt.

## À supprimer de l'ancien README

Supprimer ou corriger les affirmations suivantes si elles ne sont pas réellement implémentées :

- Application Desktop Windows PySide6, si elle n'est pas livrée dans le dépôt actuel.
- Mobile App, si elle est seulement une perspective.
- Replicate / Runway, si la version actuelle utilise ComfyUI et Ollama.
- Génération vidéo, si elle n'est pas réellement disponible dans l'interface actuelle.
- Publication automatique Facebook, Instagram ou LinkedIn, si les APIs sociales ne sont pas intégrées.
- Fine-tuning, si ce n'est pas livré dans le code.

## Formulation correcte

- La plateforme génère des images et des transformations Image-to-Image.
- Elle prépare des contenus visuels et captions/posts réutilisables manuellement sur les réseaux sociaux.
- ComfyUI et Ollama sont les services IA locaux principaux.
- Stripe sert aux paiements et crédits.
- Docker sert au backend, frontend et Redis ; ComfyUI/Ollama peuvent rester hors Docker.

## Commandes avant commit

```bash
git status --short
git diff -- README.md SECURITY.md docs/
```

Ne pas commiter si `git status` montre :

- `.env`
- `node_modules/`
- `.next/`
- `venv/`
- `ComfyUI/`
- modèles IA lourds
- fichiers `.zip`
- bases SQLite locales

## Logo officiel

Utiliser le logo réel du projet depuis `assets/ai-studio-pro-logo.png`. Ne pas utiliser de logo généré ou approximatif dans le README, les docs ou les captures de présentation.
