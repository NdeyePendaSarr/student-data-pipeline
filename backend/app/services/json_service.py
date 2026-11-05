# ============================================
# json_service.py
# Lecture de valides.json, source secondaire.
# L'import vers PostgreSQL passe par app.pipeline.
# ============================================
import json
import os

from app.database.connection import get_connection
from app.pipeline.ingestion import executer_ingestion

CHEMIN_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))),
    'data', 'valides.json'
)


def charger_json():
    """
    Lit et retourne le contenu de valides.json
    """
    with open(CHEMIN_JSON, encoding='utf-8') as f:
        return json.load(f)


def importer_selection(numeros: list):
    """
    Importe la sélection faite depuis l'interface.

    L'import déclenché par un clic emprunte exactement le même
    pipeline que l'ingestion en ligne de commande : mêmes règles de
    validation, même quarantaine, même journal d'exécution. Deux
    chemins d'entrée, une seule logique — sinon les deux finissent
    par diverger.
    """
    rapport = executer_ingestion(CHEMIN_JSON, declencheur='API',
                                 numeros=numeros)

    return {
        "id_run":         rapport['id_run'],
        "total_importes": rapport['inserees'],
        "doublons":       rapport['doublons'],
        "rejetes":        rapport['rejetees'],
        "motifs":         rapport['motifs']
    }


def lire_json_pagine(page=1, limite=5):
    """
    Retourne les étudiants du JSON qui ne sont
    pas encore dans PostgreSQL, avec pagination.
    Normalise nom et prénom à la volée.
    """
    tous = charger_json()
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT numero FROM etudiant")
        numeros_en_base = {row[0] for row in cursor.fetchall()}

        non_importes = [
            e for e in tous
            if e['numero'] not in numeros_en_base
        ]

        total     = len(non_importes)
        offset    = (page - 1) * limite
        page_data = non_importes[offset:offset + limite]

        # Normaliser nom/prénom et ajouter origine
        for e in page_data:
            e['origine'] = 'JSON'
            e['nom']     = e['nom'].upper()
            e['prenom']  = e['prenom'].title()

        return {
            "data": page_data,
            "pagination": {
                "page":        page,
                "limite":      limite,
                "total":       total,
                "total_pages": -(-total // limite)
                               if total > 0 else 0
            }
        }

    finally:
        cursor.close()
        conn.close()

def lire_json_filtre(recherche=None, classe=None):
    """
    Étudiants du JSON absents de PostgreSQL, filtrés et normalisés.

    Sert de source secondaire à la fusion : les mêmes critères que
    la requête SQL sont appliqués ici, sinon la page mélangerait
    des lignes filtrées et des lignes qui ne le sont pas.
    """
    tous = charger_json()
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT numero FROM etudiant")
        numeros_en_base = {ligne[0] for ligne in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()

    resultats = []
    terme = recherche.lower() if recherche else None

    for e in tous:
        if e['numero'] in numeros_en_base:
            continue
        if classe and e.get('classe') != classe:
            continue

        nom    = e['nom'].upper()
        prenom = e['prenom'].title()

        if terme and not any(
            terme in champ.lower()
            for champ in (nom, prenom, e['numero'], e['code'])
        ):
            continue

        moyennes = [n['moyenne'] for n in e.get('notes', {}).values()
                    if n.get('moyenne') is not None]

        resultats.append({
            **e,
            'nom':              nom,
            'prenom':           prenom,
            'libelle_classe':   e.get('classe'),
            'origine':          'JSON',
            'moyenne_generale': round(sum(moyennes) / len(moyennes), 2)
                                if moyennes else None
        })

    return resultats
