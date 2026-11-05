# ============================================
# tests/test_integration.py
# Pipeline et fusion contre un vrai PostgreSQL.
#
# Ignorés par défaut. Pour les lancer, pointer DB_* vers une base
# jetable (le schéma y est recréé) puis :
#   INTEGRATION=1 pytest tests/test_integration.py
# La CI les lance avec un service PostgreSQL 16.
# ============================================
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="INTEGRATION=1 requis (base PostgreSQL jetable)"
)

RACINE   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA   = os.path.join(RACINE, "sql", "init.sql")
VALIDES  = os.path.join(RACINE, "data", "valides.json")
INVALIDE = os.path.join(RACINE, "data", "echantillon_invalide.json")


@pytest.fixture
def base():
    """Schéma recréé avant chaque test : chacun part d'une base vide."""
    from app.database.connection import get_connection

    conn = get_connection()
    with conn, conn.cursor() as cursor, open(SCHEMA, encoding="utf-8") as f:
        cursor.execute(f.read())
    conn.close()


def compter(table):
    from app.database.connection import get_connection

    conn = get_connection()
    with conn, conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        n = cursor.fetchone()[0]
    conn.close()
    return n


def test_ingestion_idempotente(base):
    from app.pipeline.ingestion import executer_ingestion

    premier = executer_ingestion(VALIDES, limite=40)
    second  = executer_ingestion(VALIDES, limite=40)

    assert (premier["inserees"], premier["doublons"]) == (40, 0)
    assert (second["inserees"], second["doublons"]) == (0, 40)
    assert compter("etudiant") == 40
    assert compter("import_run") == 2


def test_echantillon_invalide_part_en_quarantaine(base):
    from app.pipeline.ingestion import executer_ingestion

    rapport = executer_ingestion(INVALIDE)

    assert rapport["lues"] == 8
    assert rapport["inserees"] == 1
    assert rapport["rejetees"] == 7
    assert len(rapport["motifs"]) == 7          # un motif par ligne
    assert compter("rejet") == 7
    assert compter("etudiant") == 1             # aucun orphelin


def test_import_selectif_depuis_l_api(base):
    from app.services.json_service import charger_json, importer_selection

    numeros = [e["numero"] for e in charger_json()[:3]]
    rapport = importer_selection(numeros)

    assert rapport["total_importes"] == 3
    assert importer_selection(numeros)["doublons"] == 3


def test_fusion_sans_doublon_ni_trou(base):
    """
    Parcourir toutes les pages doit rendre chaque étudiant une fois et
    une seule, y compris à la frontière entre la base et le JSON.
    """
    from app.pipeline.ingestion import executer_ingestion
    from app.services.etudiant_service import lister_fusionne
    from app.services.json_service import charger_json

    executer_ingestion(VALIDES, limite=13)      # frontière en milieu de page
    attendus = {e["numero"] for e in charger_json()}

    premiere = lister_fusionne(page=1, limite=5)
    assert premiere["pagination"]["total"] == len(attendus)

    vus = []
    for page in range(1, premiere["pagination"]["total_pages"] + 1):
        vus += [e["numero"] for e in lister_fusionne(page=page, limite=5)["data"]]

    assert len(vus) == len(set(vus))            # pas de doublon
    assert set(vus) == attendus                 # pas de trou


def test_statistiques_s_executent(base):
    from app.pipeline.ingestion import executer_ingestion
    from app.services import qualite_service, stats_service

    executer_ingestion(VALIDES, limite=40)

    classes    = stats_service.get_stats_classes()
    dispersion = {c["libelle_classe"]: c
                  for c in stats_service.get_dispersion_classes()}

    # Une seule définition de la moyenne de classe sur le tableau de bord.
    for c in classes:
        if c["nb_etudiants"]:
            assert c["moyenne_classe"] == dispersion[c["libelle_classe"]]["moyenne_classe"]

    assert stats_service.get_distribution_moyennes()["effectif"] == 40
    assert qualite_service.get_qualite_globale()["lignes_inserees"] == 40
