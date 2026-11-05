# ============================================
# routes/stats.py
# Routes dashboard et statistiques
# ============================================
from fastapi import APIRouter, Query

from app.services.stats_service import (
    get_dispersion_classes,
    get_distribution_moyennes,
    get_eleves_a_suivre,
    get_stats_classes,
    get_stats_globales,
    get_stats_matieres,
    get_top_moyennes,
)

router = APIRouter()


@router.get("/stats/globales")
def stats_globales():
    """
    Retourne les KPI globaux de l'application.
    """
    return get_stats_globales()


@router.get("/stats/classes")
def stats_classes():
    """
    Retourne les statistiques par classe.
    """
    return get_stats_classes()


@router.get("/stats/top-moyennes")
def top_moyennes():
    """
    Retourne le top 10 des meilleures moyennes.
    """
    return get_top_moyennes()


@router.get("/stats/distribution")
def distribution_moyennes():
    """
    Répartition des étudiants par tranche de moyenne,
    avec moyenne et médiane de la promotion.
    """
    return get_distribution_moyennes()


@router.get("/stats/matieres")
def stats_matieres():
    """
    Par matière : moyenne des devoirs, de l'examen et écart entre
    les deux.
    """
    return get_stats_matieres()


@router.get("/stats/eleves-a-suivre")
def eleves_a_suivre(
    limite: int   = Query(8, ge=1, le=50,
                          description="Nombre d'élèves à renvoyer"),
    seuil:  float = Query(10, ge=0, le=20,
                          description="Moyenne en dessous de laquelle "
                                      "un élève est signalé en alerte")
):
    """
    Les moyennes les plus basses, avec la matière la plus faible
    de chaque élève et un indicateur de passage sous le seuil.
    """
    return get_eleves_a_suivre(limite, seuil)


@router.get("/stats/dispersion-classes")
def dispersion_classes():
    """
    Par classe : effectif, moyenne, écart-type, minimum et maximum.
    """
    return get_dispersion_classes()
