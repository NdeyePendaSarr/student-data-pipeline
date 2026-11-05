# ============================================
# stats_service.py
# Calculs statistiques pour le dashboard
# ============================================
from app.database.connection import get_connection
from app.services.json_service import charger_json


def get_stats_globales():
    """
    Calcule les KPI globaux en combinant
    PostgreSQL et valides.json.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Nombre total en DB
        cursor.execute("SELECT COUNT(*) FROM etudiant")
        total_db = cursor.fetchone()[0]

        # Nombre archivés
        cursor.execute(
            "SELECT COUNT(*) FROM etudiant WHERE est_archive = TRUE"
        )
        total_archives = cursor.fetchone()[0]

        # Nombre valides en DB
        cursor.execute(
            "SELECT COUNT(*) FROM etudiant WHERE est_valide = TRUE"
        )
        total_valides_db = cursor.fetchone()[0]

        # Nombre invalides en DB
        cursor.execute(
            "SELECT COUNT(*) FROM etudiant WHERE est_valide = FALSE"
        )
        total_invalides_db = cursor.fetchone()[0]

        # Numéros déjà en base
        cursor.execute("SELECT numero FROM etudiant")
        numeros_en_base = {row[0] for row in cursor.fetchall()}

        # Données JSON non encore importées
        tous_json = charger_json()
        non_importes = [
            e for e in tous_json
            if e['numero'] not in numeros_en_base
        ]
        total_json = len(non_importes)

        return {
            "total_db":           total_db,
            "total_json":         total_json,
            "total_general":      total_db + total_json,
            "total_archives":     total_archives,
            "total_valides":      total_valides_db,
            "total_invalides":    total_invalides_db,
            "total_actifs":       total_db - total_archives
        }

    finally:
        cursor.close()
        conn.close()


def get_stats_classes():
    """
    Statistiques par classe :
    - nombre d'étudiants
    - moyenne générale de la classe

    La moyenne de classe est la moyenne des moyennes générales des
    élèves, comme dans get_dispersion_classes() : un élève compte
    pour un, quel que soit son nombre de matières renseignées. Une
    moyenne directe des lignes matière pondérerait les dossiers
    complets et donnerait un chiffre différent d'un graphique à
    l'autre.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH moyennes AS (
                SELECT
                    e.id_etudiant,
                    e.id_classe,
                    AVG(r.moyenne_matiere) AS moyenne
                FROM etudiant e
                LEFT JOIN resultat_matiere r
                    ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant, e.id_classe
            )
            SELECT
                c.libelle_classe,
                COUNT(mo.id_etudiant)                AS nb_etudiants,
                ROUND(AVG(mo.moyenne)::numeric, 2)   AS moyenne_classe
            FROM classe c
            LEFT JOIN moyennes mo ON mo.id_classe = c.id_classe
            GROUP BY c.libelle_classe
            ORDER BY c.libelle_classe
        """)

        colonnes = [desc[0] for desc in cursor.description]
        lignes   = cursor.fetchall()

        resultats = []
        for ligne in lignes:
            row = dict(zip(colonnes, ligne, strict=True))
            row['moyenne_classe'] = float(row['moyenne_classe']) \
                if row['moyenne_classe'] else 0
            resultats.append(row)

        return resultats

    finally:
        cursor.close()
        conn.close()


def get_top_moyennes():
    """
    Top 10 des étudiants avec les meilleures
    moyennes générales.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                e.nom,
                e.prenom,
                c.libelle_classe,
                ROUND(AVG(r.moyenne_matiere)::numeric, 2)
                    AS moyenne_generale
            FROM etudiant e
            JOIN classe c ON e.id_classe = c.id_classe
            JOIN resultat_matiere r
                ON r.id_etudiant = e.id_etudiant
            WHERE e.est_archive = FALSE
            GROUP BY e.id_etudiant, e.nom, e.prenom,
                     c.libelle_classe
            ORDER BY moyenne_generale DESC
            LIMIT 10
        """)

        colonnes = [desc[0] for desc in cursor.description]
        lignes   = cursor.fetchall()

        resultats = []
        for ligne in lignes:
            row = dict(zip(colonnes, ligne, strict=True))
            row['moyenne_generale'] = float(row['moyenne_generale'])
            row['nom_complet'] = f"{row['nom']} {row['prenom']}"
            resultats.append(row)

        return resultats

    finally:
        cursor.close()
        conn.close()


def get_distribution_moyennes():
    """
    Repartit les etudiants par tranche de moyenne generale.

    Un comptage global dit combien d'eleves il y a ; une distribution
    dit ou se situe la promotion par rapport a la barre des 10.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH moyennes AS (
                SELECT
                    e.id_etudiant,
                    AVG(r.moyenne_matiere) AS moyenne
                FROM etudiant e
                JOIN resultat_matiere r
                    ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant
            )
            SELECT
                CASE
                    WHEN moyenne <  8 THEN 0
                    WHEN moyenne < 10 THEN 1
                    WHEN moyenne < 12 THEN 2
                    WHEN moyenne < 14 THEN 3
                    WHEN moyenne < 16 THEN 4
                    ELSE                   5
                END                       AS rang,
                COUNT(*)                  AS nb_etudiants
            FROM moyennes
            GROUP BY rang
            ORDER BY rang
        """)
        comptes = {ligne[0]: ligne[1] for ligne in cursor.fetchall()}

        libelles = ['0 à 8', '8 à 10', '10 à 12',
                    '12 à 14', '14 à 16', '16 à 20']
        tranches = [
            {
                "tranche":      libelles[rang],
                "nb_etudiants": comptes.get(rang, 0),
                # En dessous de 10 : c'est la barre d'admission.
                "sous_la_barre": rang < 2
            }
            for rang in range(6)
        ]

        # Mediane et moyenne de promotion, pour situer la distribution.
        cursor.execute("""
            WITH moyennes AS (
                SELECT AVG(r.moyenne_matiere) AS moyenne
                FROM etudiant e
                JOIN resultat_matiere r
                    ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant
            )
            SELECT
                ROUND(AVG(moyenne)::numeric, 2),
                ROUND(PERCENTILE_CONT(0.5)
                      WITHIN GROUP (ORDER BY moyenne)::numeric, 2),
                COUNT(*)
            FROM moyennes
        """)
        moyenne, mediane, effectif = cursor.fetchone()

        return {
            "tranches": tranches,
            "moyenne":  float(moyenne) if moyenne else 0,
            "mediane":  float(mediane) if mediane else 0,
            "effectif": effectif or 0
        }

    finally:
        cursor.close()
        conn.close()


def get_stats_matieres():
    """
    Par matiere : moyenne des devoirs, note d'examen et ecart.

    Un ecart fortement negatif signale une matiere ou les eleves
    tiennent le controle continu mais decrochent a l'examen.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH par_resultat AS (
                SELECT
                    r.id_resultat,
                    r.id_matiere,
                    r.note_examen,
                    AVG(d.note_devoir) AS moyenne_devoirs
                FROM resultat_matiere r
                JOIN etudiant e
                    ON e.id_etudiant = r.id_etudiant
                    AND e.est_archive = FALSE
                LEFT JOIN devoir d
                    ON d.id_resultat = r.id_resultat
                GROUP BY r.id_resultat, r.id_matiere, r.note_examen
            )
            SELECT
                m.libelle_matiere,
                COUNT(*)                                        AS nb_etudiants,
                ROUND(AVG(p.moyenne_devoirs)::numeric, 2)       AS moyenne_devoirs,
                ROUND(AVG(p.note_examen)::numeric, 2)           AS moyenne_examen,
                ROUND((AVG(p.note_examen)
                       - AVG(p.moyenne_devoirs))::numeric, 2)   AS ecart
            FROM par_resultat p
            JOIN matiere m ON m.id_matiere = p.id_matiere
            GROUP BY m.libelle_matiere
            ORDER BY ecart ASC
        """)

        colonnes = [desc[0] for desc in cursor.description]
        resultats = []
        for ligne in cursor.fetchall():
            row = dict(zip(colonnes, ligne, strict=True))
            for cle in ('moyenne_devoirs', 'moyenne_examen', 'ecart'):
                row[cle] = float(row[cle]) if row[cle] is not None else 0
            resultats.append(row)

        return resultats

    finally:
        cursor.close()
        conn.close()


def get_eleves_a_suivre(limite=8, seuil=10):
    """
    Les moyennes les plus basses, avec la matiere qui penalise le plus.

    Savoir combien d'eleves sont en difficulte ne sert a rien si l'on
    ne sait pas lesquels, ni sur quoi les faire travailler. On renvoie
    le bas du classement plutot que le seul filtre "sous le seuil" :
    une promotion entierement au-dessus de 10 a quand meme des eleves
    a surveiller, et le seuil sert alors a marquer l'alerte.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH moyennes AS (
                SELECT
                    e.id_etudiant,
                    e.nom,
                    e.prenom,
                    c.libelle_classe,
                    AVG(r.moyenne_matiere) AS moyenne
                FROM etudiant e
                JOIN classe c ON c.id_classe = e.id_classe
                JOIN resultat_matiere r
                    ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant, e.nom, e.prenom, c.libelle_classe
            ),
            matiere_la_plus_faible AS (
                SELECT DISTINCT ON (r.id_etudiant)
                    r.id_etudiant,
                    m.libelle_matiere,
                    r.moyenne_matiere
                FROM resultat_matiere r
                JOIN matiere m ON m.id_matiere = r.id_matiere
                ORDER BY r.id_etudiant, r.moyenne_matiere ASC
            )
            SELECT
                mo.nom,
                mo.prenom,
                mo.libelle_classe,
                ROUND(mo.moyenne::numeric, 2)      AS moyenne_generale,
                f.libelle_matiere                  AS matiere_faible,
                ROUND(f.moyenne_matiere::numeric, 2) AS note_faible
            FROM moyennes mo
            JOIN matiere_la_plus_faible f
                ON f.id_etudiant = mo.id_etudiant
            ORDER BY mo.moyenne ASC
            LIMIT %s
        """, (limite,))

        colonnes = [desc[0] for desc in cursor.description]
        resultats = []
        for ligne in cursor.fetchall():
            row = dict(zip(colonnes, ligne, strict=True))
            row['moyenne_generale'] = float(row['moyenne_generale'])
            row['note_faible']      = float(row['note_faible'])
            row['nom_complet']      = f"{row['nom']} {row['prenom']}"
            row['sous_la_barre']    = row['moyenne_generale'] < seuil
            resultats.append(row)

        return resultats

    finally:
        cursor.close()
        conn.close()


def get_dispersion_classes():
    """
    Par classe : effectif, moyenne, dispersion, minimum et maximum.

    Deux classes a 12 de moyenne n'ont pas le meme profil selon
    qu'elles sont homogenes ou eclatees : l'ecart-type le dit.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH moyennes AS (
                SELECT
                    e.id_etudiant,
                    e.id_classe,
                    AVG(r.moyenne_matiere) AS moyenne
                FROM etudiant e
                JOIN resultat_matiere r
                    ON r.id_etudiant = e.id_etudiant
                WHERE e.est_archive = FALSE
                GROUP BY e.id_etudiant, e.id_classe
            )
            SELECT
                c.libelle_classe,
                COUNT(mo.id_etudiant)                            AS nb_etudiants,
                ROUND(AVG(mo.moyenne)::numeric, 2)               AS moyenne_classe,
                ROUND(COALESCE(STDDEV_POP(mo.moyenne), 0)::numeric, 2)
                                                                 AS ecart_type,
                ROUND(MIN(mo.moyenne)::numeric, 2)               AS moyenne_min,
                ROUND(MAX(mo.moyenne)::numeric, 2)               AS moyenne_max
            FROM classe c
            LEFT JOIN moyennes mo ON mo.id_classe = c.id_classe
            GROUP BY c.libelle_classe
            HAVING COUNT(mo.id_etudiant) > 0
            ORDER BY c.libelle_classe
        """)

        colonnes = [desc[0] for desc in cursor.description]
        resultats = []
        for ligne in cursor.fetchall():
            row = dict(zip(colonnes, ligne, strict=True))
            for cle in ('moyenne_classe', 'ecart_type',
                        'moyenne_min', 'moyenne_max'):
                row[cle] = float(row[cle]) if row[cle] is not None else 0
            resultats.append(row)

        return resultats

    finally:
        cursor.close()
        conn.close()
