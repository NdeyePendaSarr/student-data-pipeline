# ============================================
# services/qualite_service.py
# Observabilité du pipeline : exécutions, rejets, complétude
# ============================================
from app.database.connection import get_connection


def _lignes_en_dicts(cursor):
    colonnes = [description[0] for description in cursor.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in cursor.fetchall()]


def get_historique_runs(limite=10):
    """
    Dernières exécutions du pipeline, la plus récente d'abord.

    Un import qui n'a laissé aucune trace est un import qu'on ne
    peut ni auditer ni rejouer : ce journal est la mémoire du
    pipeline.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id_run,
                source,
                declencheur,
                statut,
                TO_CHAR(demarre_le, 'DD/MM/YYYY HH24:MI') AS demarre_le,
                ROUND(EXTRACT(EPOCH FROM (termine_le - demarre_le))::numeric, 2)
                                                          AS duree_secondes,
                lignes_lues,
                lignes_inserees,
                lignes_doublons,
                lignes_rejetees
            FROM import_run
            ORDER BY id_run DESC
            LIMIT %s
        """, (limite,))

        runs = _lignes_en_dicts(cursor)
        for run in runs:
            run['duree_secondes'] = (float(run['duree_secondes'])
                                     if run['duree_secondes'] is not None
                                     else None)
        return runs

    finally:
        cursor.close()
        conn.close()


def get_rejets_par_motif():
    """
    Répartition des lignes en quarantaine par cause.

    Compter les rejets ne sert qu'à une chose : savoir quelle règle
    casse le plus, donc quoi corriger en premier à la source.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                motif,
                COUNT(*)                        AS nb_rejets,
                MIN(LEFT(detail, 120))          AS exemple
            FROM rejet
            GROUP BY motif
            ORDER BY nb_rejets DESC, motif
        """)
        return _lignes_en_dicts(cursor)

    finally:
        cursor.close()
        conn.close()


def get_qualite_globale():
    """
    Indicateurs de qualité sur l'ensemble des ingestions.

    Le taux d'acceptation rapporte les lignes chargées aux lignes
    lues ; la complétude mesure, sur les lignes chargées, la part
    de celles dont chaque matière du référentiel est renseignée.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                COALESCE(SUM(lignes_lues), 0)     AS lues,
                COALESCE(SUM(lignes_inserees), 0) AS inserees,
                COALESCE(SUM(lignes_doublons), 0) AS doublons,
                COALESCE(SUM(lignes_rejetees), 0) AS rejetees,
                COUNT(*)                          AS nb_runs
            FROM import_run
            WHERE statut = 'SUCCES'
        """)
        lues, inserees, doublons, rejetees, nb_runs = cursor.fetchone()

        cursor.execute("""
            WITH attendu AS (SELECT COUNT(*) AS n FROM matiere),
            par_etudiant AS (
                SELECT
                    e.id_etudiant,
                    COUNT(r.id_resultat) AS matieres_renseignees
                FROM etudiant e
                LEFT JOIN resultat_matiere r
                       ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant
            )
            SELECT
                COUNT(*)                                       AS total,
                COUNT(*) FILTER (
                    WHERE matieres_renseignees = (SELECT n FROM attendu)
                )                                              AS complets,
                ROUND(AVG(matieres_renseignees)::numeric, 2)   AS moyenne_matieres,
                (SELECT n FROM attendu)                        AS matieres_attendues
            FROM par_etudiant
        """)
        total, complets, moyenne_matieres, attendues = cursor.fetchone()

        traitees = (inserees or 0) + (rejetees or 0)

        return {
            "nb_runs":            nb_runs or 0,
            "lignes_lues":        lues or 0,
            "lignes_inserees":    inserees or 0,
            "lignes_doublons":    doublons or 0,
            "lignes_rejetees":    rejetees or 0,
            # Les doublons ne sont ni une réussite ni un échec :
            # le taux se calcule sur les lignes réellement traitées.
            "taux_acceptation":   round(inserees / traitees * 100, 1)
                                  if traitees else 100.0,
            "dossiers_complets":  complets or 0,
            "dossiers_total":     total or 0,
            "taux_completude":    round(complets / total * 100, 1)
                                  if total else 0.0,
            "matieres_attendues": attendues or 0,
            "matieres_moyenne":   float(moyenne_matieres)
                                  if moyenne_matieres else 0.0
        }

    finally:
        cursor.close()
        conn.close()
