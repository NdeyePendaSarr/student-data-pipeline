#!/usr/bin/env bash
# ============================================
# setup.sh — Installation du projet
# Environnement Python, dépendances, schéma PostgreSQL
# et construction de l'interface React.
# ============================================
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Environnement virtuel Python"
cd "$RACINE/backend"
python3 -m venv venv
./venv/bin/pip install --upgrade pip --quiet
./venv/bin/pip install -r requirements.txt --quiet

if [ ! -f .env ]; then
    echo "==> Création de backend/.env à partir du modèle"
    cp .env.example .env
    echo "    Renseignez vos identifiants PostgreSQL dans backend/.env,"
    echo "    puis relancez ce script."
    exit 0
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

echo "==> Schéma PostgreSQL ($DB_NAME)"
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" -p "$DB_PORT" \
    -U "$DB_USER" -d "$DB_NAME" \
    -f sql/init.sql

# Chargement partiel : le reste du fichier demeure dans le JSON,
# qui garde son rôle de source secondaire (voir README).
echo "==> Ingestion initiale des données (40 premières lignes)"
./venv/bin/python -m app.pipeline --limite 40

echo "==> Interface React"
cd "$RACINE/frontend-react"
npm install
npm run build

echo "==> Terminé. Démarrez avec : ./scripts/run.sh"
