# ============================================
# etudiant_service.py
# Logique métier — requêtes SQL pour les étudiants
# ============================================
from app.database.connection import get_connection


def _construire_filtres(recherche=None, classe=None,
                        archive=False, valide=None):
    """
    Construit la clause WHERE et la liste de valeurs associee.

    Factorise le filtrage partage par compter_etudiants() et
    lister_etudiants() : les deux doivent toujours appliquer
    exactement les memes criteres, sinon la pagination ment.

    Seule la structure de la clause est interpolee ; toutes les
    valeurs restent passees en parametres (%s) a psycopg2.
    """
    conditions = ["e.est_archive = %s"]
    valeurs    = [archive]

    if recherche:
        conditions.append(
            "(LOWER(e.nom) LIKE %s OR LOWER(e.prenom) LIKE %s "
            "OR LOWER(e.numero) LIKE %s OR LOWER(e.code) LIKE %s)"
        )
        terme = f"%{recherche.lower()}%"
        valeurs.extend([terme, terme, terme, terme])

    if classe:
        conditions.append("c.libelle_classe = %s")
        valeurs.append(classe)

    if valide is not None:
        conditions.append("e.est_valide = %s")
        valeurs.append(valide == 'true')

    return " AND ".join(conditions), valeurs


def compter_etudiants(recherche=None, classe=None,
                       archive=False, valide=None):
    """
    Compte le nombre total d'étudiants selon les filtres.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        where, valeurs = _construire_filtres(
            recherche=recherche, classe=classe,
            archive=archive, valide=valide
        )

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM etudiant e
            JOIN classe c ON e.id_classe = c.id_classe
            WHERE {where}
        """, valeurs)

        return cursor.fetchone()[0]

    finally:
        cursor.close()
        conn.close()


def lister_etudiants(page=1, limite=5, recherche=None,
                     classe=None, archive=False, valide=None):
    """
    Retourne une page d'étudiants avec leur moyenne générale.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        offset = (page - 1) * limite

        where, valeurs = _construire_filtres(
            recherche=recherche, classe=classe,
            archive=archive, valide=valide
        )

        cursor.execute(f"""
            SELECT
                e.id_etudiant,
                e.code,
                e.numero,
                e.nom,
                e.prenom,
                e.date_naissance,
                c.libelle_classe,
                e.est_archive,
                e.est_valide,
                e.source,
                e.created_at,
                ROUND(AVG(r.moyenne_matiere)::numeric, 2)
                    AS moyenne_generale
            FROM etudiant e
            JOIN classe c ON e.id_classe = c.id_classe
            LEFT JOIN resultat_matiere r
                ON r.id_etudiant = e.id_etudiant
            WHERE {where}
            GROUP BY e.id_etudiant, e.code, e.numero, e.nom,
                     e.prenom, e.date_naissance, c.libelle_classe,
                     e.est_archive, e.est_valide,
                     e.source, e.created_at
            ORDER BY e.nom, e.prenom
            LIMIT %s OFFSET %s
        """, valeurs + [limite, offset])

        colonnes = [desc[0] for desc in cursor.description]
        lignes   = cursor.fetchall()

        etudiants = []
        for ligne in lignes:
            etudiant = dict(zip(colonnes, ligne, strict=True))
            etudiant['date_naissance'] = str(etudiant['date_naissance'])
            etudiant['created_at']     = str(etudiant['created_at'])
            etudiant['moyenne_generale'] = float(
                etudiant['moyenne_generale']
            ) if etudiant['moyenne_generale'] else None
            etudiant['origine'] = 'DB'
            etudiants.append(etudiant)

        return etudiants

    finally:
        cursor.close()
        conn.close()


def get_etudiant_par_id(id_etudiant):
    """
    Retourne un étudiant complet avec toutes ses notes.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                e.id_etudiant, e.code, e.numero, e.nom, e.prenom,
                e.date_naissance, c.libelle_classe, e.est_archive,
                e.est_valide, e.source, e.created_at
            FROM etudiant e
            JOIN classe c ON e.id_classe = c.id_classe
            WHERE e.id_etudiant = %s
        """, (id_etudiant,))

        colonnes = [desc[0] for desc in cursor.description]
        ligne    = cursor.fetchone()

        if ligne is None:
            return None

        etudiant = dict(zip(colonnes, ligne, strict=True))
        etudiant['date_naissance'] = str(etudiant['date_naissance'])
        etudiant['created_at']     = str(etudiant['created_at'])
        etudiant['origine']        = 'DB'

        cursor.execute("""
            SELECT
                m.libelle_matiere,
                r.note_examen,
                r.moyenne_matiere,
                r.id_resultat
            FROM resultat_matiere r
            JOIN matiere m ON m.id_matiere = r.id_matiere
            WHERE r.id_etudiant = %s
            ORDER BY m.libelle_matiere
        """, (id_etudiant,))

        notes = {}
        for row in cursor.fetchall():
            matiere, examen, moyenne, id_resultat = row

            cursor.execute("""
                SELECT note_devoir FROM devoir
                WHERE id_resultat = %s
                ORDER BY id_devoir
            """, (id_resultat,))

            devoirs = [float(d[0]) for d in cursor.fetchall()]

            notes[matiere] = {
                "devoirs": devoirs,
                "examen":  float(examen),
                "moyenne": float(moyenne)
            }

        etudiant['notes'] = notes
        return etudiant

    finally:
        cursor.close()
        conn.close()


def creer_etudiant(data):
    """
    Insère un nouvel étudiant avec ses notes dans PostgreSQL.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id_classe FROM classe WHERE libelle_classe = %s",
            (data.classe,)
        )
        resultat = cursor.fetchone()
        if resultat is None:
            raise ValueError(f"Classe '{data.classe}' inexistante")
        id_classe = resultat[0]

        cursor.execute(
            "SELECT id_etudiant FROM etudiant WHERE numero = %s",
            (data.numero,)
        )
        if cursor.fetchone() is not None:
            raise ValueError(f"Le numéro '{data.numero}' existe déjà")

        cursor.execute("""
            INSERT INTO etudiant
                (code, numero, nom, prenom, date_naissance,
                 id_classe, est_archive, est_valide, source)
            VALUES (%s, %s, %s, %s, %s, %s,
                    FALSE, TRUE, 'SAISIE_MANUELLE')
            RETURNING id_etudiant
        """, (
            data.code, data.numero, data.nom,
            data.prenom, data.date_naissance, id_classe
        ))
        id_etudiant = cursor.fetchone()[0]

        for matiere_nom, note in data.notes.items():
            cursor.execute(
                "SELECT id_matiere FROM matiere "
                "WHERE libelle_matiere = %s",
                (matiere_nom,)
            )
            res_matiere = cursor.fetchone()
            if res_matiere is None:
                continue

            cursor.execute("""
                INSERT INTO resultat_matiere
                    (note_examen, moyenne_matiere,
                     id_etudiant, id_matiere)
                VALUES (%s, %s, %s, %s)
                RETURNING id_resultat
            """, (
                note.examen, note.moyenne,
                id_etudiant, res_matiere[0]
            ))
            id_resultat = cursor.fetchone()[0]

            for valeur in note.devoirs:
                cursor.execute(
                    "INSERT INTO devoir (note_devoir, id_resultat) "
                    "VALUES (%s, %s)",
                    (valeur, id_resultat)
                )

        conn.commit()
        return get_etudiant_par_id(id_etudiant)

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def modifier_etudiant(id_etudiant, data):
    """
    Met à jour uniquement les champs fournis.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id_etudiant FROM etudiant WHERE id_etudiant = %s",
            (id_etudiant,)
        )
        if cursor.fetchone() is None:
            return None

        champs  = []
        valeurs = []

        if data.nom is not None:
            champs.append("nom = %s")
            valeurs.append(data.nom)

        if data.prenom is not None:
            champs.append("prenom = %s")
            valeurs.append(data.prenom)

        if data.date_naissance is not None:
            champs.append("date_naissance = %s")
            valeurs.append(data.date_naissance)

        if data.classe is not None:
            cursor.execute(
                "SELECT id_classe FROM classe "
                "WHERE libelle_classe = %s",
                (data.classe,)
            )
            resultat = cursor.fetchone()
            if resultat is None:
                raise ValueError(
                    f"Classe '{data.classe}' inexistante"
                )
            champs.append("id_classe = %s")
            valeurs.append(resultat[0])

        if not champs:
            return get_etudiant_par_id(id_etudiant)

        valeurs.append(id_etudiant)

        cursor.execute(f"""
            UPDATE etudiant
            SET {', '.join(champs)}
            WHERE id_etudiant = %s
        """, valeurs)

        conn.commit()
        return get_etudiant_par_id(id_etudiant)

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def archiver_etudiant(id_etudiant):
    """
    Archive logiquement un étudiant.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT est_archive FROM etudiant "
            "WHERE id_etudiant = %s",
            (id_etudiant,)
        )
        ligne = cursor.fetchone()

        if ligne is None:
            return None, "introuvable"
        if ligne[0]:
            return None, "deja_archive"

        cursor.execute("""
            UPDATE etudiant SET est_archive = TRUE
            WHERE id_etudiant = %s
        """, (id_etudiant,))

        conn.commit()
        return True, "archive"

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def restaurer_etudiant(id_etudiant):
    """
    Restaure un étudiant archivé.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT est_archive FROM etudiant "
            "WHERE id_etudiant = %s",
            (id_etudiant,)
        )
        ligne = cursor.fetchone()

        if ligne is None:
            return None, "introuvable"
        if not ligne[0]:
            return None, "pas_archive"

        cursor.execute("""
            UPDATE etudiant SET est_archive = FALSE
            WHERE id_etudiant = %s
        """, (id_etudiant,))

        conn.commit()
        return True, "restaure"

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def lister_fusionne(page=1, limite=5, recherche=None, classe=None,
                    archive=False, valide=None, source='tous'):
    """
    Une page d'étudiants, fusionnée par le backend.

    Le cahier des charges décrit ce comportement : le serveur reçoit
    le numéro de page, applique les filtres, interroge PostgreSQL,
    complète si nécessaire avec le fichier JSON, puis ne retourne que
    les lignes de la page demandée. Le frontend n'a rien à recoller.

    PostgreSQL est la source principale : la liste globale est donc
    la base d'abord, le JSON ensuite. Le JSON reprend exactement là
    où la base s'arrête, ce qui évite le doublon et le trou à la
    frontière entre les deux sources.

    Archives et validité n'existent que côté base : dans ces cas le
    JSON n'est pas interrogé.
    """
    from app.services.json_service import lire_json_filtre

    offset          = (page - 1) * limite
    json_pertinent  = source != 'db' and not archive and valide is None

    if source == 'json':
        if not json_pertinent:
            lignes, total = [], 0
        else:
            tout   = lire_json_filtre(recherche, classe)
            total  = len(tout)
            lignes = tout[offset:offset + limite]
    else:
        total_db = compter_etudiants(recherche, classe, archive, valide)
        lignes   = lister_etudiants(page, limite, recherche,
                                    classe, archive, valide)
        total    = total_db

        if json_pertinent:
            tout_json = lire_json_filtre(recherche, classe)
            total    += len(tout_json)

            restant = limite - len(lignes)
            if restant > 0:
                debut  = max(0, offset - total_db)
                lignes = lignes + tout_json[debut:debut + restant]

    return {
        "data": lignes,
        "pagination": {
            "page":        page,
            "limite":      limite,
            "total":       total,
            "total_pages": -(-total // limite) if total > 0 else 1
        }
    }
