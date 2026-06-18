@echo off
chcp 65001 >nul
echo ==========================================
echo    AI Studio Pro - Installation
echo ==========================================
echo.

REM Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé!
    echo Veuillez installer Python 3.11+ depuis https://python.org
    pause
    exit /b 1
)

echo [1/4] Python détecté
echo.

REM Backend
echo [2/4] Installation du backend...
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Échec de l'installation du backend
    pause
    exit /b 1
)
cd ..
echo [OK] Backend installé
echo.

REM Desktop
echo [3/4] Installation de l'application desktop...
cd desktop
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Échec de l'installation du desktop
    pause
    exit /b 1
)
cd ..
echo [OK] Desktop installé
echo.

REM Configuration
echo [4/4] Configuration...
if not exist backend\.env (
    copy backend\.env.example backend\.env
    echo [INFO] Fichier .env créé. Veuillez le configurer.
)

echo.
echo ==========================================
echo    Installation terminée!
echo ==========================================
echo.
echo Pour démarrer:
echo   1. Backend: cd backend ^&^& venv\Scripts\activate ^&^& uvicorn main:app --reload
echo   2. Desktop: cd desktop ^&^& venv\Scripts\activate ^&^& python main.py
echo.
pause
