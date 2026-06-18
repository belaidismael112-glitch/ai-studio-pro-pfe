#!/bin/bash

echo "=========================================="
echo "   AI Studio Pro - Installation"
echo "=========================================="
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "[ERREUR] Python n'est pas installé!"
    echo "Veuillez installer Python 3.11+"
    exit 1
fi

echo "[1/4] Python détecté"
echo ""

# Backend
echo "[2/4] Installation du backend..."
cd backend || exit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERREUR] Échec de l'installation du backend"
    exit 1
fi
cd ..
echo "[OK] Backend installé"
echo ""

# Desktop
echo "[3/4] Installation de l'application desktop..."
cd desktop || exit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERREUR] Échec de l'installation du desktop"
    exit 1
fi
cd ..
echo "[OK] Desktop installé"
echo ""

# Configuration
echo "[4/4] Configuration..."
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "[INFO] Fichier .env créé. Veuillez le configurer."
fi

echo ""
echo "=========================================="
echo "   Installation terminée!"
echo "=========================================="
echo ""
echo "Pour démarrer:"
echo "  1. Backend: cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo "  2. Desktop: cd desktop && source venv/bin/activate && python main.py"
echo ""
