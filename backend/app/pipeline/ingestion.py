# ============================================
# pipeline/ingestion.py
# Extraction, validation, quarantaine, chargement
# ============================================
import json
import os
from datetime import datetime

from app.database.connection import get_connection
from app.regles import code_valide, est_note, moyenne_matiere, numero_valide

# Motifs de rejet. Une catégorie stable permet de compter les
# rejets par cause et de savoir quoi corriger en priorité ;
# le détail, lui, décrit le cas précis.
MOTIFS = {
    'CHAMP_MANQUANT':   "Champ obligatoire absent",
    'FORMAT_CODE':      "Code hors format attendu",
    'FORMAT_NUMERO':    "Numéro hors format attendu",
    'FORMAT_NOM':       "Nom ou prénom non conforme",
    'FORMAT_DATE':      "Date de naissance illisible",
    'CLASSE_INCONNUE':  "Classe absente du référentiel",
    'NOTE_HORS_BORNES': "Note en dehors de l'intervalle 0–20",
    'NOTES_ABSENTES':   "Aucune note exploitable",
}

CHAMPS_OBLIGATOIRES = ('code', 'numero', 'nom', 'prenom',
                       'date_naissance', 'classe')

FORMATS_DATE = ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y')


class LigneRejetee(Exception):
    """Ligne écartée : porte son motif et son détail."""

    def __init__(self, motif, detail):
        super().__init__(detail)
        self.motif  = motif
        self.detail = detail


# ── Validation ──────────────────────────────

def _convertir_date(valeur):
    for format_essaye in FORMATS_DATE:
        try:
            return datetime.strptime(str(valeur), format_essaye).date()
        except (ValueError, TypeError):
            continue
    raise LigneRejetee('FORMAT_DATE', f"Date illisible : {valeur!r}")


def valider_ligne(brut):
    """
    Contrôle une ligne du fichier et renvoie sa version normalisée.

    Les règles reprennent celles du projet Python amont : code sur
    trois lettres puis trois chiffres, numéro alphanumérique de sept
    caractères, notes bornées entre 0 et 20. Une ligne qui échoue
    lève LigneRejetee et part en quarantaine plutôt que d'être
    perdue en silence.
    """
    manquants = [c for c in CHAMPS_OBLIGATOIRES if not brut.get(c)]
    if manquants:
        raise LigneRejetee('CHAMP_MANQUANT',
                           f"Champs absents : {', '.join(manquants)}")

    code = str(brut['code']).strip().upper()
    if not code_valide(code):
        raise LigneRejetee('FORMAT_CODE', f"Code invalide : {code!r}")

    numero = str(brut['numero']).strip().upper()
    if not numero_valide(numero):
        raise LigneRejetee('FORMAT_NUMERO', f"Numéro invalide : {numero!r}")

    nom    = str(brut['nom']).strip()
    prenom = str(brut['prenom']).strip()
    if len(nom) < 2 or not nom[0].isalpha():
        raise LigneRejetee('FORMAT_NOM', f"Nom invalide : {nom!r}")
    if len(prenom) < 3 or not prenom[0].isalpha():
        raise LigneRejetee('FORMAT_NOM', f"Prénom invalide : {prenom!r}")

    date_naissance = _convertir_date(brut['date_naissance'])

    notes = {}
    for matiere, donnees in (brut.get('notes') or {}).items():
        devoirs = donnees.get('devoirs') or []
        examen  = donnees.get('examen')
        if examen is None or not devoirs:
            continue

        for note in [*devoirs, examen]:
            if not est_note(note):
                raise LigneRejetee(
                    'NOTE_HORS_BORNES',
                    f"{matiere} : note {note!r} hors de l'intervalle 0–20"
                )

        moyenne = donnees.get('moyenne')
        if moyenne is None:
            moyenne = moyenne_matiere(devoirs, examen)
        elif not est_note(moyenne):
            raise LigneRejetee(
                'NOTE_HORS_BORNES',
                f"{matiere} : moyenne {moyenne!r} hors de l'intervalle 0–20"
            )

        notes[matiere] = {
            'devoirs': list(devoirs),
            'examen':  examen,
            'moyenne': round(float(moyenne), 2)
        }

    if not notes:
        raise LigneRejetee('NOTES_ABSENTES',
                           "Aucune matière avec devoirs et examen")

    return {
        'code':           code,
        'numero':         numero,
        'nom':            nom.upper(),
        'prenom':         prenom.title(),
        'date_naissance': date_naissance,
        'classe':         str(brut['classe']).strip(),
        'notes':          notes
    }


# ── Journal d'exécution ─────────────────────

def _ouvrir_run(cursor, source, declencheur):
    cursor.execute("""
        INSERT INTO import_run (source, declencheur, statut)
        VALUES (%s, %s, 'EN_COURS')
        RETURNING id_run
    """, (source, declencheur))
    return cursor.fetchone()[0]


def _fermer_run(cursor, id_run, statut, compteurs, message=None):
    cursor.execute("""
        UPDATE import_run
           SET statut          = %s,
               termine_le      = NOW(),
               lignes_lues     = %s,
               lignes_inserees = %s,
               lignes_doublons = %s,
               lignes_rejetees = %s,
               message         = %s
         WHERE id_run = %s
    """, (statut, compteurs['lues'], compteurs['inserees'],
          compteurs['doublons'], compteurs['rejetees'], message, id_run))


def _enregistrer_rejet(cursor, id_run, brut, motif, detail):
    cursor.execute("""
        INSERT INTO rejet (id_run, numero, code, motif, detail, charge_utile)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        id_run,
        str(brut.get('numero'))[:40] if brut.get('numero') else None,
        str(brut.get('code'))[:40] if brut.get('code') else None,
        motif, detail, json.dumps(brut, ensure_ascii=False, default=str)
    ))


# ── Chargement ──────────────────────────────

def _charger_etudiant(cursor, ligne, id_run, referentiel_classes,
                      referentiel_matieres):
    id_classe = referentiel_classes.get(ligne['classe'])
    if id_classe is None:
        raise LigneRejetee('CLASSE_INCONNUE',
                           f"Classe absente du référentiel : {ligne['classe']!r}")

    # Contrôle fait avant tout INSERT : une ligne rejetée ici ne doit
    # laisser aucun étudiant orphelin en base.
    notes = {m: d for m, d in ligne['notes'].items()
             if m in referentiel_matieres}
    if not notes:
        raise LigneRejetee(
            'NOTES_ABSENTES',
            "Aucune matière du référentiel : "
            f"{', '.join(ligne['notes'])}"
        )

    cursor.execute("""
        INSERT INTO etudiant
            (code, numero, nom, prenom, date_naissance,
             id_classe, est_archive, est_valide, source, id_run)
        VALUES (%s, %s, %s, %s, %s, %s, FALSE, TRUE, 'IMPORT_JSON', %s)
        RETURNING id_etudiant
    """, (ligne['code'], ligne['numero'], ligne['nom'], ligne['prenom'],
          ligne['date_naissance'], id_classe, id_run))
    id_etudiant = cursor.fetchone()[0]

    for matiere, donnees in notes.items():
        id_matiere = referentiel_matieres[matiere]
        cursor.execute("""
            INSERT INTO resultat_matiere
                (note_examen, moyenne_matiere, id_etudiant, id_matiere)
            VALUES (%s, %s, %s, %s)
            RETURNING id_resultat
        """, (donnees['examen'], donnees['moyenne'], id_etudiant, id_matiere))
        id_resultat = cursor.fetchone()[0]

        for note in donnees['devoirs']:
            cursor.execute(
                "INSERT INTO devoir (note_devoir, id_resultat) VALUES (%s, %s)",
                (note, id_resultat)
            )


# ── Point d'entrée ──────────────────────────

def executer_ingestion(chemin, declencheur='CLI', numeros=None,
                       limite=None):
    """
    Exécute une ingestion complète et renvoie son rapport.

    Le pipeline est idempotent : `numero` est la clé métier, et une
    ligne déjà présente en base est comptée comme doublon puis
    ignorée. Relancer l'ingestion sur le même fichier n'insère donc
    rien de nouveau et ne crée pas de duplicata.

    Chaque ligne suit l'un de trois chemins, et un seul : insérée,
    comptée comme doublon, ou mise en quarantaine avec son motif.
    La somme des trois vaut toujours le nombre de lignes lues.

    `limite` ne charge que les n premières lignes du fichier. Le
    reste demeure dans le JSON, qui garde ainsi son rôle de source
    secondaire : c'est lui qui complète l'affichage tant que la base
    ne suffit pas, et c'est de là que partent les imports.
    """
    if not os.path.isfile(chemin):
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    with open(chemin, encoding='utf-8') as fichier:
        lignes = json.load(fichier)

    if numeros is not None:
        voulus = set(numeros)
        lignes = [brut for brut in lignes
                  if str(brut.get('numero')).upper() in voulus
                  or brut.get('numero') in voulus]

    if limite is not None:
        lignes = lignes[:limite]

    conn   = get_connection()
    cursor = conn.cursor()
    compteurs = {'lues': len(lignes), 'inserees': 0,
                 'doublons': 0, 'rejetees': 0}
    motifs_rencontres = {}

    try:
        id_run = _ouvrir_run(cursor, os.path.basename(chemin), declencheur)

        cursor.execute("SELECT libelle_classe, id_classe FROM classe")
        classes = dict(cursor.fetchall())
        cursor.execute("SELECT libelle_matiere, id_matiere FROM matiere")
        matieres = dict(cursor.fetchall())
        cursor.execute("SELECT numero FROM etudiant")
        deja_en_base = {ligne[0] for ligne in cursor.fetchall()}

        for brut in lignes:
            try:
                ligne = valider_ligne(brut)

                if ligne['numero'] in deja_en_base:
                    compteurs['doublons'] += 1
                    continue

                _charger_etudiant(cursor, ligne, id_run, classes, matieres)
                deja_en_base.add(ligne['numero'])
                compteurs['inserees'] += 1

            except LigneRejetee as rejet:
                _enregistrer_rejet(cursor, id_run, brut,
                                   rejet.motif, rejet.detail)
                compteurs['rejetees'] += 1
                motifs_rencontres[rejet.motif] = \
                    motifs_rencontres.get(rejet.motif, 0) + 1

        _fermer_run(cursor, id_run, 'SUCCES', compteurs)
        conn.commit()

        return {
            'id_run':      id_run,
            'source':      os.path.basename(chemin),
            'declencheur': declencheur,
            'statut':      'SUCCES',
            **compteurs,
            'motifs': motifs_rencontres
        }

    except Exception as erreur:
        conn.rollback()
        # Le run échoué est journalisé dans une transaction propre :
        # sans cela, le rollback effacerait la trace de l'échec.
        try:
            cursor.execute("""
                INSERT INTO import_run
                    (source, declencheur, statut, termine_le,
                     lignes_lues, message)
                VALUES (%s, %s, 'ECHEC', NOW(), %s, %s)
            """, (os.path.basename(chemin), declencheur,
                  compteurs['lues'], str(erreur)[:500]))
            conn.commit()
        except Exception:
            conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()
