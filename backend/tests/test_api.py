# ============================================
# tests/test_api.py
# Contrats HTTP vérifiables sans base de données : bornes des
# paramètres et comportement du health check.
# ============================================
import pytest
from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


@pytest.mark.parametrize("requete", [
    "/api/v1/json/etudiants?limite=0",
    "/api/v1/json/etudiants?page=0",
    "/api/v1/json/etudiants?limite=10000",
    "/api/v1/etudiants?source=autre",
])
def test_parametres_hors_bornes_refuses_en_422(requete):
    assert client.get(requete).status_code == 422


def test_import_d_une_selection_vide_refuse():
    assert client.post("/api/v1/import/json", json=[]).status_code == 422


def test_health_renvoie_503_sans_divulguer_l_erreur(monkeypatch):
    def connexion_impossible():
        raise RuntimeError("password authentication failed for user secret")

    monkeypatch.setattr(main, "get_connection", connexion_impossible)
    reponse = client.get("/api/v1/health")

    assert reponse.status_code == 503
    assert "secret" not in reponse.text


def test_health_ok(monkeypatch):
    class ConnexionFactice:
        def close(self):
            pass

    monkeypatch.setattr(main, "get_connection", ConnexionFactice)
    reponse = client.get("/api/v1/health")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "ok"
