# ============================================
# tests/test_regles.py
# Règles partagées par l'API et le pipeline : formats ASCII,
# bornes des notes, formule de moyenne.
# ============================================
import pytest

from app.models.etudiant import EtudiantModifier, NoteMatiere
from app.pipeline.ingestion import LigneRejetee, _charger_etudiant, valider_ligne
from app.regles import code_valide, est_note, moyenne_matiere, numero_valide

from .test_pipeline import ligne, motif_du_rejet

# ── Formats ASCII stricts ───────────────────

@pytest.mark.parametrize("code", ["ÉÉÉ123", "AAD١٢٣", "AAD²34"])
def test_code_unicode_refuse(code):
    assert not code_valide(code)
    assert motif_du_rejet(ligne(code=code)) == "FORMAT_CODE"


@pytest.mark.parametrize("numero", ["H5G32YÉ", "H5G32Y١"])
def test_numero_unicode_refuse(numero):
    assert not numero_valide(numero)


def test_code_herite_en_minuscules_normalise_par_le_pipeline():
    assert valider_ligne(ligne(code="aad004"))["code"] == "AAD004"


# ── Notes ───────────────────────────────────

@pytest.mark.parametrize("valeur", [True, False, "12", None, 20.5, -0.1])
def test_valeurs_qui_ne_sont_pas_des_notes(valeur):
    assert not est_note(valeur)


def test_booleen_refuse_comme_note_par_le_pipeline():
    donnees = ligne(notes={"Math": {"devoirs": [True], "examen": 10}})
    assert motif_du_rejet(donnees) == "NOTE_HORS_BORNES"


def test_moyenne_fournie_hors_bornes_refusee():
    donnees = ligne(notes={"Math": {"devoirs": [10], "examen": 10,
                                    "moyenne": 35}})
    assert motif_du_rejet(donnees) == "NOTE_HORS_BORNES"


# ── Moyenne calculée par le serveur ─────────

def test_formule_de_moyenne():
    # (moyenne des devoirs 14.5 + 2 x 10) / 3
    assert moyenne_matiere([14, 15], 10) == 11.5


def test_moyenne_envoyee_par_le_client_ignoree():
    note = NoteMatiere(devoirs=[14, 15], examen=10, moyenne=3)
    assert note.moyenne == 11.5


def test_moyenne_absente_calculee():
    assert NoteMatiere(devoirs=[12, 18], examen=12).moyenne == 13.0


def test_api_et_pipeline_appliquent_la_meme_formule():
    donnees = ligne(notes={"Math": {"devoirs": [12, 17], "examen": 9}})
    via_pipeline = valider_ligne(donnees)["notes"]["Math"]["moyenne"]
    via_api = NoteMatiere(devoirs=[12, 17], examen=9).moyenne
    assert via_pipeline == via_api


# ── Modification : mêmes règles qu'à la création ──

@pytest.mark.parametrize("champs", [{"nom": "4diallo"}, {"nom": "   "},
                                    {"prenom": "1awa"}])
def test_modification_refuse_ce_que_la_creation_refuse(champs):
    with pytest.raises(ValueError):
        EtudiantModifier(**champs)


# ── Matières hors référentiel ───────────────

class CurseurEspion:
    """Enregistre les requêtes : aucune ne doit partir si la ligne est rejetée."""

    def __init__(self):
        self.requetes = []

    def execute(self, sql, params=None):
        self.requetes.append(sql)

    def fetchone(self):
        return (1,)


def test_aucune_matiere_du_referentiel_rejet_sans_insert():
    curseur = CurseurEspion()
    valide = valider_ligne(ligne(notes={
        "Maths": {"devoirs": [10], "examen": 10}
    }))
    with pytest.raises(LigneRejetee) as capture:
        _charger_etudiant(curseur, valide, id_run=1,
                          referentiel_classes={"6emeA": 1},
                          referentiel_matieres={"Math": 1})
    assert capture.value.motif == "NOTES_ABSENTES"
    assert curseur.requetes == []


def test_matiere_inconnue_ignoree_si_une_autre_est_valide():
    curseur = CurseurEspion()
    valide = valider_ligne(ligne(notes={
        "Math":  {"devoirs": [10], "examen": 10},
        "Maths": {"devoirs": [10], "examen": 10},
    }))
    _charger_etudiant(curseur, valide, id_run=1,
                      referentiel_classes={"6emeA": 1},
                      referentiel_matieres={"Math": 1})
    inserts_resultat = [r for r in curseur.requetes
                        if "INSERT INTO resultat_matiere" in r]
    assert len(inserts_resultat) == 1
