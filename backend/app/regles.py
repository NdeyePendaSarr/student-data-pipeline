# ============================================
# regles.py
# Règles métier partagées par l'API et le pipeline d'ingestion.
# Un seul endroit pour les formats et la formule de moyenne :
# sinon la saisie manuelle et l'import finissent par diverger.
# ============================================
import re

# ASCII strict : str.isalpha() / isdigit() accepteraient « É » ou « ١ ».
MOTIF_CODE   = re.compile(r'[A-Z]{3}[0-9]{3}')
MOTIF_NUMERO = re.compile(r'[A-Z0-9]{7}')

NOTE_MIN, NOTE_MAX = 0, 20


def code_valide(code: str) -> bool:
    return MOTIF_CODE.fullmatch(code) is not None


def numero_valide(numero: str) -> bool:
    return MOTIF_NUMERO.fullmatch(numero) is not None


def est_note(valeur) -> bool:
    """Nombre entre 0 et 20. Un booléen n'est pas une note."""
    return (isinstance(valeur, int | float)
            and not isinstance(valeur, bool)
            and NOTE_MIN <= valeur <= NOTE_MAX)


def moyenne_matiere(devoirs, examen) -> float:
    """
    Formule du projet amont : la moyenne des devoirs compte pour
    un tiers, l'examen pour deux tiers.
    """
    return round((sum(devoirs) / len(devoirs) + 2 * examen) / 3, 2)
