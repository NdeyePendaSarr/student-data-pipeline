# ============================================
# routes/qualite.py
# Observabilité du pipeline d'ingestion
# ============================================
from fastapi import APIRouter, Query

from app.services.qualite_service import (
    get_historique_runs,
    get_qualite_globale,
    get_rejets_par_motif,
)

router = APIRouter()


@router.get("/qualite/runs")
def historique_runs(limite: int = Query(default=10, ge=1, le=100)):
    """Journal des dernières exécutions du pipeline."""
    return get_historique_runs(limite)


@router.get("/qualite/rejets")
def rejets_par_motif():
    """Lignes en quarantaine, regroupées par motif."""
    return get_rejets_par_motif()


@router.get("/qualite/indicateurs")
def indicateurs_qualite():
    """Taux d'acceptation, complétude et volumes ingérés."""
    return get_qualite_globale()
