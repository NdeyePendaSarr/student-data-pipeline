# ============================================
# config.py
# Lecture des variables d'environnement
# ============================================
import os

from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Variables de connexion à la base de données
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "integrateur_web_db")
DB_USER     = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Origines autorisées par CORS.
# Le frontend étant servi par FastAPI lui-même, la valeur par défaut
# est restrictive ; on n'élargit que si CORS_ORIGINS est défini.
CORS_ORIGINS = [
    origine.strip()
    for origine in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origine.strip()
]
