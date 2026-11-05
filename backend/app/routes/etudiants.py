# ============================================
# routes/etudiants.py
# Routes API pour les étudiants
# ============================================
from fastapi import APIRouter, HTTPException, Query

from app.models.etudiant import EtudiantCreer, EtudiantModifier
from app.services import etudiant_service

router = APIRouter()


@router.get("/etudiants")
def liste_etudiants(
    page:      int  = Query(default=1, ge=1),
    limite:    int  = Query(default=5, ge=1, le=500),
    recherche: str  = Query(default=None),
    classe:    str  = Query(default=None),
    archive:   bool = Query(default=False),
    valide:    str  = Query(default=None),
    source:    str  = Query(default='tous', pattern='^(tous|db|json)$')
):
    """
    Retourne une page d'étudiants, fusionnée côté serveur.

    PostgreSQL est la source principale ; le fichier `valides.json`
    complète la page lorsque la base ne fournit pas assez de lignes.
    Chaque ligne porte son origine (`DB` ou `JSON`).

    Paramètres :
    - page      : numéro de page (défaut 1)
    - limite    : lignes par page (défaut 5)
    - recherche : filtre par nom, prénom, numéro ou code
    - classe    : filtre par classe
    - archive   : afficher les archivés (défaut False)
    - valide    : 'true' ou 'false' pour filtrer par validité
    - source    : 'tous', 'db' ou 'json'
    """
    return etudiant_service.lister_fusionne(
        page=page, limite=limite,
        recherche=recherche, classe=classe,
        archive=archive, valide=valide, source=source
    )


@router.get("/etudiants/{id_etudiant}")
def detail_etudiant(id_etudiant: int):
    etudiant = etudiant_service.get_etudiant_par_id(id_etudiant)
    if etudiant is None:
        raise HTTPException(status_code=404,
                            detail="Étudiant introuvable")
    return etudiant


@router.post("/etudiants", status_code=201)
def creer_etudiant(data: EtudiantCreer):
    try:
        etudiant = etudiant_service.creer_etudiant(data)
        return etudiant
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/etudiants/{id_etudiant}")
def modifier_etudiant(id_etudiant: int, data: EtudiantModifier):
    try:
        etudiant = etudiant_service.modifier_etudiant(
            id_etudiant, data
        )
        if etudiant is None:
            raise HTTPException(status_code=404,
                                detail="Étudiant introuvable")
        return etudiant
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/etudiants/{id_etudiant}/archive")
def archiver_etudiant(id_etudiant: int):
    resultat, statut = etudiant_service.archiver_etudiant(id_etudiant)
    if statut == "introuvable":
        raise HTTPException(status_code=404,
                            detail="Étudiant introuvable")
    if statut == "deja_archive":
        raise HTTPException(status_code=400,
                            detail="Étudiant déjà archivé")
    return {"message": f"Étudiant {id_etudiant} archivé"}


@router.post("/etudiants/{id_etudiant}/restore")
def restaurer_etudiant(id_etudiant: int):
    resultat, statut = etudiant_service.restaurer_etudiant(id_etudiant)
    if statut == "introuvable":
        raise HTTPException(status_code=404,
                            detail="Étudiant introuvable")
    if statut == "pas_archive":
        raise HTTPException(status_code=400,
                            detail="Étudiant non archivé")
    return {"message": f"Étudiant {id_etudiant} restauré"}
