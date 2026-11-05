"""
Pipeline d'ingestion du fichier JSON vers PostgreSQL.

Extraction du fichier, validation ligne à ligne, mise en quarantaine
des lignes non conformes, chargement des lignes retenues et
journalisation de l'exécution.
"""
from app.pipeline.ingestion import MOTIFS, executer_ingestion

__all__ = ['executer_ingestion', 'MOTIFS']
