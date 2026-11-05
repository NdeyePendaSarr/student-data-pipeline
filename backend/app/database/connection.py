# ============================================
# connection.py
# Gestion de la connexion PostgreSQL
# ============================================
import psycopg2

from app.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def get_connection():
    """
    Crée et retourne une connexion à PostgreSQL.
    À appeler à chaque fois qu'on a besoin d'interagir
    avec la base de données.
    """
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return connection
