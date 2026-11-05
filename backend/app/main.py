# ============================================
# main.py
# Point d'entrée de l'application FastAPI
# ============================================
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS
from app.database.connection import get_connection
from app.routes import etudiants, import_json, qualite, stats

journal = logging.getLogger(__name__)

app = FastAPI(
    title="Student Data Pipeline - API",
    description="Ingestion, réconciliation et observabilité de données "
                "étudiants",
    version="1.0.0"
)

# Configuration CORS
# Liste blanche pilotée par la variable d'environnement CORS_ORIGINS.
# allow_origins=["*"] avec allow_credentials=True est refusé par les
# navigateurs et ouvre inutilement l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

# ── Frontend ────────────────────────────────
# L'interface est une application React construite par Vite.
# `npm run build` produit frontend-react/dist, que FastAPI sert ici.
RACINE       = os.path.join(os.path.dirname(__file__), '..', '..')
FRONTEND_DIR = os.path.abspath(os.path.join(RACINE, 'frontend-react', 'dist'))
INDEX        = os.path.join(FRONTEND_DIR, 'index.html')

if os.path.isdir(os.path.join(FRONTEND_DIR, 'assets')):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIR, 'assets')),
        name="assets"
    )

# Enregistrement des routes API
app.include_router(etudiants.router,   prefix="/api/v1")
app.include_router(qualite.router, prefix="/api/v1", tags=["Qualité"])
app.include_router(stats.router,       prefix="/api/v1")
app.include_router(import_json.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health_check():
    # 503 si la base est injoignable : un superviseur ou un load
    # balancer lit le code HTTP, pas le corps. Le détail de l'erreur
    # (hôte, utilisateur…) reste dans les logs du serveur.
    try:
        conn = get_connection()
        conn.close()
    except Exception:
        journal.exception("Base de données injoignable")
        return JSONResponse(
            status_code=503,
            content={"status": "error",
                     "message": "Base de données injoignable"}
        )
    return {
        "status": "ok",
        "message": "Serveur et base de données opérationnels"
    }


def servir_application():
    """
    Renvoie l'application React.

    Le routage est géré côté navigateur : toutes les pages de
    l'interface partagent le même index.html.
    """
    if not os.path.isfile(INDEX):
        raise HTTPException(
            status_code=503,
            detail="Interface non construite. Lancez : "
                   "cd frontend-react && npm install && npm run build"
        )
    return FileResponse(INDEX)


@app.get("/")
def page_eleves():
    return servir_application()


@app.get("/dashboard")
def page_tableau_de_bord():
    return servir_application()
