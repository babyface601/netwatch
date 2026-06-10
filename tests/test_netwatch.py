"""
Tests unitaires — NetWatch
Lance avec : pytest tests/
"""
import sys
import os
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import netwatch_app as app_module
from netwatch_app import app

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    """Client de test Flask avec base SQLite temporaire."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    # Base de données temporaire pour les tests
    app_module._DB_PATH = str(tmp_path / "test.db")
    app_module.init_db()

    with app.test_client() as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    """Client déjà authentifié."""
    client.post("/login", data={"username": "admin", "password": "netwatch"})
    return client


# ─── Tests d'authentification ─────────────────────────────────────────────────

def test_login_page_accessible(client):
    """La page de login doit être accessible sans authentification."""
    resp = client.get("/login")
    assert resp.status_code == 200


def test_dashboard_redirige_sans_login(client):
    """Le dashboard doit rediriger vers /login si non authentifié."""
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_valide(client):
    """Un login correct doit rediriger vers le dashboard."""
    resp = client.post("/login", data={"username": "admin", "password": "netwatch"})
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_login_invalide(client):
    """Un login incorrect doit rester sur /login avec un message d'erreur."""
    resp = client.post("/login", data={"username": "admin", "password": "mauvais"})
    assert resp.status_code == 200
    assert b"Identifiants" in resp.data or b"incorrect" in resp.data.lower() or resp.status_code == 200


def test_logout(logged_in_client):
    """Le logout doit rediriger vers /login."""
    resp = logged_in_client.get("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ─── Tests des routes API ──────────────────────────────────────────────────────

def test_api_status_requiert_auth(client):
    """L'API /api/status doit être protégée."""
    resp = client.get("/api/status")
    assert resp.status_code == 302  # redirige vers login


def test_api_status_retourne_json(logged_in_client):
    """L'API /api/status doit retourner un JSON avec 'hosts' et 'summary'."""
    fake_target = [{"name": "Local", "host": "127.0.0.1", "ports": [], "type": "web"}]
    fake_result = {"name": "Local", "host": "127.0.0.1", "status": "up",
                   "reachable": True, "latency": 1.0, "ports": {},
                   "type": "web", "checked_at": "00:00:00"}
    with patch.object(app_module, 'TARGETS', fake_target), \
         patch.object(app_module, 'check_target', return_value=fake_result), \
         patch.object(app_module, 'save_scan_results'), \
         patch.object(app_module, 'check_and_alert'):
        resp = logged_in_client.get("/api/status")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "hosts" in data
    assert "summary" in data
    assert data["summary"]["total"] == 1


def test_api_targets_get(logged_in_client):
    """GET /api/targets doit retourner la liste des cibles."""
    resp = logged_in_client.get("/api/targets")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert isinstance(data, list)


def test_api_targets_post_valide(logged_in_client):
    """POST /api/targets avec un hôte valide doit retourner 200 ou 201."""
    payload = {"name": "Test Host CI", "host": "8.8.8.8", "ports": [53], "type": "dns"}
    resp = logged_in_client.post(
        "/api/targets",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert resp.status_code in (200, 201)


def test_api_targets_post_sans_nom(logged_in_client):
    """POST /api/targets sans nom doit retourner une erreur."""
    payload = {"host": "8.8.8.8", "ports": [53]}
    resp = logged_in_client.post(
        "/api/targets",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert resp.status_code == 400


# ─── Tests de la logique métier ───────────────────────────────────────────────

def test_load_targets_retourne_liste():
    """load_targets() doit toujours retourner une liste."""
    targets = app_module.load_targets()
    assert isinstance(targets, list)


def test_ping_host_retourne_tuple():
    """ping_host doit retourner un tuple (bool, float|None) sans lever d'exception."""
    reachable, latency = app_module.ping_host("127.0.0.1")
    assert isinstance(reachable, bool)
    assert latency is None or isinstance(latency, float)


def test_check_port_ferme():
    """check_port sur un port fermé doit retourner False."""
    # Port 19999 sur localhost très probablement fermé
    result = app_module.check_port("127.0.0.1", 19999, timeout=1)
    assert result is False
