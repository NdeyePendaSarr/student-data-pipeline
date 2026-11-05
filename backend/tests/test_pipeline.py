# ============================================
# tests/test_pipeline.py
# Règles de validation du pipeline d'ingestion.
# Aucune base de données requise : on teste la fonction de
# validation seule, qui décide de ce qui passe et de ce qui
# part en quarantaine.
# ============================================
import pytest

from app.pipeline.ingestion import MOTIFS, LigneRejetee, valider_ligne


def ligne(**surcharges):
    base = {
        "code": "AAD004",
        "numero": "H5G32YR",
        "nom": "diallo",
        "prenom": "nourou",
        "date_naissance": "02/01/2012",
        "classe": "6emeA",
        "notes": {
            "Math": {"devoirs": [14, 15], "examen": 10, "moyenne": 11.5}
        }
    }
    base.update(surcharges)
    return base


def motif_du_rejet(donnees):
    with pytest.raises(LigneRejetee) as capture:
        valider_ligne(donnees)
    return capture.value.motif


# ── Lignes acceptées ────────────────────────

def test_ligne_conforme_est_acceptee():
    resultat = valider_ligne(ligne())
    assert resultat["numero"] == "H5G32YR"
    assert resultat["nom"] == "DIALLO"
    assert resultat["prenom"] == "Nourou"


def test_date_normalisee_quel_que_soit_le_format():
    for saisie in ("02/01/2012", "2012-01-02", "02-01-2012"):
        resultat = valider_ligne(ligne(date_naissance=saisie))
        assert str(resultat["date_naissance"]) == "2012-01-02"


def test_moyenne_recalculee_si_absente():
    # Formule du projet amont : (moyenne des devoirs + 2 x examen) / 3
    donnees = ligne(notes={
        "Math": {"devoirs": [12, 18], "examen": 12}
    })
    assert valider_ligne(donnees)["notes"]["Math"]["moyenne"] == 13.0


def test_matiere_incomplete_est_ignoree_sans_rejeter_la_ligne():
    donnees = ligne(notes={
        "Math":     {"devoirs": [14], "examen": 12, "moyenne": 12.67},
        "Francais": {"devoirs": [], "examen": None}
    })
    retenues = valider_ligne(donnees)["notes"]
    assert list(retenues) == ["Math"]


# ── Lignes mises en quarantaine ─────────────

@pytest.mark.parametrize("champ", ["code", "numero", "nom",
                                   "prenom", "date_naissance", "classe"])
def test_champ_obligatoire_absent(champ):
    assert motif_du_rejet(ligne(**{champ: ""})) == "CHAMP_MANQUANT"


@pytest.mark.parametrize("code", ["AAD04", "AA1004", "AAD0045"])
def test_code_hors_format(code):
    assert motif_du_rejet(ligne(code=code)) == "FORMAT_CODE"


@pytest.mark.parametrize("numero", ["H5G32Y", "H5G32YRS", "H5G-2YR"])
def test_numero_hors_format(numero):
    assert motif_du_rejet(ligne(numero=numero)) == "FORMAT_NUMERO"


def test_nom_commencant_par_un_chiffre():
    assert motif_du_rejet(ligne(nom="4diallo")) == "FORMAT_NOM"


def test_date_illisible():
    assert motif_du_rejet(ligne(date_naissance="32/13/2005")) == "FORMAT_DATE"


@pytest.mark.parametrize("note", [-1, 21, 45])
def test_note_hors_bornes(note):
    donnees = ligne(notes={"Math": {"devoirs": [10], "examen": note}})
    assert motif_du_rejet(donnees) == "NOTE_HORS_BORNES"


def test_aucune_note_exploitable():
    assert motif_du_rejet(ligne(notes={})) == "NOTES_ABSENTES"


# ── Référentiel des motifs ──────────────────

def test_chaque_motif_leve_est_documente():
    """
    Un motif inconnu du référentiel rendrait le tableau de bord
    qualité illisible : tous doivent y être décrits.
    """
    leves = {
        motif_du_rejet(ligne(code="AA1")),
        motif_du_rejet(ligne(numero="TROPLONG")),
        motif_du_rejet(ligne(nom="")),
        motif_du_rejet(ligne(prenom="4x")),
        motif_du_rejet(ligne(date_naissance="32/13/2005")),
        motif_du_rejet(ligne(notes={})),
        motif_du_rejet(ligne(notes={"Math": {"devoirs": [30], "examen": 10}})),
    }
    assert leves <= set(MOTIFS)
